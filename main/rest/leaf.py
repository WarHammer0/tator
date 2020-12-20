import logging
from collections import defaultdict

from django.db import transaction

from ..models import Leaf
from ..models import LeafType
from ..models import Project
from ..models import database_qs
from ..models import database_query_ids
from ..search import TatorSearch
from ..schema import LeafSuggestionSchema
from ..schema import LeafListSchema
from ..schema import LeafDetailSchema
from ..schema import parse

from ._base_views import BaseListView
from ._base_views import BaseDetailView
from ._leaf_query import get_leaf_queryset
from ._attributes import AttributeFilterMixin
from ._attributes import patch_attributes
from ._attributes import bulk_patch_attributes
from ._attributes import validate_attributes
from ._util import computeRequiredFields
from ._util import check_required_fields
from ._permissions import ProjectViewOnlyPermission
from ._permissions import ProjectFullControlPermission

logger = logging.getLogger(__name__)

class LeafSuggestionAPI(BaseDetailView):
    """ Rest Endpoint compatible with devbridge suggestion format.

    <https://github.com/kraaden/autocomplete>
    """
    schema = LeafSuggestionSchema()
    permission_classes = [ProjectViewOnlyPermission]
    http_method_names = ['get']

    def _get(self, params):
        minLevel=int(params.get('minLevel', 1))
        startsWith=params.get('query', None)
        ancestor=params['ancestor']
        query = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(dict))))
        query['size'] = 10
        query['sort']['_exact_treeleaf_name'] = 'asc'
        query['query']['bool']['filter'] = [
            {'match': {'_dtype': {'query': 'leaf'}}},
            {'range': {'_treeleaf_depth': {'gte': minLevel}}},
            {'query_string': {'query': f'{startsWith}* AND _treeleaf_path:{ancestor}*'}},
        ]
        ids, _ = TatorSearch().search(params['project'], query)
        queryset = list(Leaf.objects.filter(pk__in=ids))

        suggestions=[]
        for idx,match in enumerate(queryset):
            group = params['ancestor']
            if match.parent:
                group = match.parent.name

            suggestion={
                "value": match.name,
                "group": group,
                "data": {}
            }

            if 'alias' in match.attributes:
                suggestion["data"]["alias"] = match.attributes['alias']

            catAlias=None
            if match.parent:
                if match.parent.attributes:
                    catAlias=match.parent.attributes.get("alias",None)
                if catAlias != None:
                    suggestion["group"] = f'{suggestion["group"]} ({catAlias})'


            suggestions.append(suggestion);

        def functor(elem):
            return elem["group"]

        suggestions.sort(key=functor)
        return suggestions

class LeafListAPI(BaseListView, AttributeFilterMixin):
    """ Interact with a list of leaves.

        Tree leaves are used to define label hierarchies that can be used for autocompletion
        of string attribute types.
    """
    schema = LeafListSchema()
    permission_classes = [ProjectFullControlPermission]
    http_method_names = ['get', 'post', 'patch', 'delete']
    entity_type = LeafType # Needed by attribute filter mixin

    def _get(self, params):
        self.validate_attribute_filter(params)
        postgres_params = ['project', 'type', 'operation']
        use_es = any([key not in postgres_params for key in params])

        # Get the leaf list.
        if use_es:
            response_data = []
            leaf_ids, leaf_count, _ = get_leaf_queryset(params)
            if self.operation == 'count':
                response_data = {'count': len(leaf_ids)}
            elif len(leaf_ids) > 0:
                response_data = database_query_ids('main_leaf', leaf_ids, 'id')
        else:
            qs = Leaf.objects.filter(project=params['project'])
            if 'type' in params:
                qs = qs.filter(meta=params['type'])
            if self.operation == 'count':
                response_data = {'count': qs.count()}
            else:
                response_data = database_qs(qs.order_by('id'))
        return response_data

    def _post(self, params):
        # Check that we are getting a leaf list.
        if 'body' in params:
            leaf_specs = params['body']
        else:
            raise Exception('Leaf creation requires list of leaves!')

        # Find unique foreign keys.
        meta_ids = set([leaf['type'] for leaf in leaf_specs])

        # Make foreign key querysets.
        meta_qs = LeafType.objects.filter(pk__in=meta_ids)

        # Construct foreign key dictionaries.
        project = Project.objects.get(pk=params['project'])
        metas = {obj.id:obj for obj in meta_qs.iterator()}

        # Get required fields for attributes.
        required_fields = {id_:computeRequiredFields(metas[id_]) for id_ in meta_ids}
        for val in required_fields.values():
            val[0].pop('path', None) # Remove path since it is computed.
        attr_specs = [check_required_fields(required_fields[leaf['type']][0],
                                            required_fields[leaf['type']][2],
                                            leaf)
                      for leaf in leaf_specs]
       
        # Create the leaf objects.
        leaves = []
        create_buffer = []
        for leaf_spec, attrs in zip(leaf_specs, attr_specs):
            parent = None
            if 'parent' in leaf_spec:
                if leaf_spec['parent'] is not None:
                    parent = Leaf.objects.get(pk=leaf_spec['parent'])
                    if parent.project.pk != params['project']:
                        raise Exception(f"Specified parent ID is not in project {params['project']}")
            leaf = Leaf(project=project,
                        meta=metas[leaf_spec['type']],
                        attributes=attrs,
                        created_by=self.request.user,
                        modified_by=self.request.user,
                        name=leaf_spec['name'],
                        parent=parent)
            leaf.path = leaf.computePath()
            create_buffer.append(leaf)
            if len(create_buffer) > 1000:
                leaves += Leaf.objects.bulk_create(create_buffer)
                create_buffer = []
        leaves += Leaf.objects.bulk_create(create_buffer)

        # Build ES documents.
        ts = TatorSearch()
        documents = []
        for leaf in leaves:
            documents += ts.build_document(leaf)
            if len(documents) > 1000:
                ts.bulk_add_documents(documents)
                documents = []
        ts.bulk_add_documents(documents)

        # Return created IDs.
        ids = [leaf.id for leaf in leaves]
        return {'message': f'Successfully created {len(ids)} leaves!', 'id': ids}

    def _delete(self, params):
        self.validate_attribute_filter(params)
        leaf_ids, leaf_count, query = get_leaf_queryset(params)
        if len(leaf_ids) > 0:
            qs = Leaf.objects.filter(pk__in=leaf_ids)
            qs._raw_delete(qs.db)
            TatorSearch().delete(self.kwargs['project'], query)
        return {'message': f'Successfully deleted {len(leaf_ids)} leaves!'}

    def _patch(self, params):
        self.validate_attribute_filter(params)
        leaf_ids, leaf_count, query = get_leaf_queryset(params)
        if len(leaf_ids) > 0:
            qs = Leaf.objects.filter(pk__in=leaf_ids)
            new_attrs = validate_attributes(params, qs[0])
            bulk_patch_attributes(new_attrs, qs)
            TatorSearch().update(self.kwargs['project'], qs[0].meta, query, new_attrs)
        return {'message': f'Successfully updated {len(leaf_ids)} leaves!'}

    def get_queryset(self):
        params = parse(self.request)
        self.validate_attribute_filter(params)
        leaf_ids, leaf_count, _ = get_leaf_queryset(params)
        queryset = Leaf.objects.filter(pk__in=leaf_ids)
        return queryset

class LeafDetailAPI(BaseDetailView):
    """ Interact with individual leaf.

        Tree leaves are used to define label hierarchies that can be used for autocompletion
        of string attribute types.
    """
    schema = LeafDetailSchema()
    permission_classes = [ProjectFullControlPermission]
    lookup_field = 'id'

    def _get(self, params):
        return database_qs(Leaf.objects.filter(pk=params['id']))[0]

    @transaction.atomic
    def _patch(self, params):
        obj = Leaf.objects.get(pk=params['id'])

        # Patch common attributes.
        if 'name' in params:
            obj.name = params['name']
            obj.save()
        new_attrs = validate_attributes(params, obj)
        obj = patch_attributes(new_attrs, obj)

        obj.save()
        return {'message': 'Leaf {params["id"]} successfully updated!'}

    def _delete(self, params):
        Leaf.objects.get(pk=params['id']).delete()
        return {'message': 'Leaf {params["id"]} successfully deleted!'}

    def get_queryset(self):
        return Leaf.objects.all()

