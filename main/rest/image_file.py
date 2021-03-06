from django.db import transaction
from django.http import Http404

from ..models import Media
from ..models import Resource
from ..models import safe_delete
from ..models import drop_media_from_resource
from ..schema import ImageFileListSchema
from ..schema import ImageFileDetailSchema

from ._base_views import BaseListView
from ._base_views import BaseDetailView
from ._permissions import ProjectTransferPermission

class ImageFileListAPI(BaseListView):
    schema = ImageFileListSchema()
    permission_classes = [ProjectTransferPermission]
    http_method_names = ['get', 'post']

    def _get(self, params):
        media = Media.objects.get(pk=params['id'])
        role = params['role']
        response_data = []
        if media.media_files:
            if role in media.media_files:
                response_data = media.media_files[role]
        return response_data

    @transaction.atomic
    def _post(self, params):
        media = Media.objects.select_for_update().get(pk=params['id'])
        role = params['role']
        body = params['body']
        index = params.get('index')
        if not media.media_files:
            media.media_files = {}
        if role not in media.media_files:
            media.media_files[role] = []
        if index is None:
            media.media_files[role].append(body)
        else:
            if index >= len(media.media_files[role]):
                raise ValueError(f"Supplied index {index} is larger than current array size "
                                 f"{len(media.media_files[role])}")
            media.media_files[role].insert(index, body)
        media.save()
        Resource.add_resource(body['path'], media)
        return {'message': f"Media file in media object {media.id} created!"}

    def get_queryset(self):
        return Media.objects.all()

class ImageFileDetailAPI(BaseDetailView):
    schema = ImageFileDetailSchema()
    permission_classes = [ProjectTransferPermission]
    lookup_field = 'id'
    http_method_names = ['get', 'patch', 'delete']

    def _get(self, params):
        media = Media.objects.get(pk=params['id'])
        role = params['role']
        index = params['index']
        response_data = []
        if media.media_files:
            if role in media.media_files:
                response_data = media.media_files[role]
        if index >= len(response_data):
            raise ValueError(f"Supplied index {index} is larger than current array size "
                             f"{len(response_data)}")
        return response_data[index]

    @transaction.atomic
    def _patch(self, params):
        media = Media.objects.select_for_update().get(pk=params['id'])
        role = params['role']
        body = params['body']
        index = params['index']
        if not media.media_files:
            raise Http404
        if role not in media.media_files:
            raise Http404
        if index >= len(media.media_files[role]):
            raise ValueError(f"Supplied index {index} is larger than current array size "
                             f"{len(media.media_files[role])}")
        old_path = media.media_files[role][index]['path']
        new_path = body['path']
        media.media_files[role][index] = body
        media.save()
        if old_path != new_path:
            drop_media_from_resource(old_path, media)
            safe_delete(old_path)
            Resource.add_resource(new_path, media)
        return {'message': f"Media file in media object {media.id} successfully updated!"}

    @transaction.atomic
    def _delete(self, params):
        media = Media.objects.select_for_update().get(pk=params['id'])
        role = params['role']
        index = params['index']
        if not media.media_files:
            raise Http404
        if role not in media.media_files:
            raise Http404
        if index >= len(media.media_files[role]):
            raise ValueError(f"Supplied index {index} is larger than current array size "
                             f"{len(media.media_files[role])}")
        deleted = media.media_files[role].pop(index)
        media.save()
        drop_media_from_resource(deleted['path'], media)
        safe_delete(deleted['path'])
        return {'message': f'Media file in media object {params["id"]} successfully deleted!'}

    def get_queryset(self):
        return Media.objects.all()
