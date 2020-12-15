import logging
import os
import time
import subprocess
import json
import datetime
import shutil

from progressbar import progressbar,ProgressBar
from dateutil.parser import parse

from main.models import *
from main.search import TatorSearch
from main.search import mediaFileSizes

from django.conf import settings
from django.db.models import F

from elasticsearch import Elasticsearch
from elasticsearch.helpers import streaming_bulk

logger = logging.getLogger(__name__)

""" Utility scripts for data management in django-shell """

def clearDataAboutMedia(id):
    """
    Given an id Delete all states, localizations that apply.

    :param id: The id of the media element to purge metadata about.
    """
    #Delete all states by hitting associations which auto delete states
    qs = State.objects.filter(media__in=[id])
    qs.delete()

    #Delete all localizations
    qs = Localization.objects.filter(media=id)
    qs.delete()

def updateProjectTotals(force=False):
    projects = Project.objects.all()
    for project in projects:
        temp_files = TemporaryFile.objects.filter(project=project)
        files = Media.objects.filter(project=project)
        if (files.count() + temp_files.count() != project.num_files) or force:
            project.num_files = files.count() + temp_files.count()
            project.size = 0
            for file in temp_files.iterator():
                if file.path:
                    if os.path.exists(file.path):
                        project.size += os.path.getsize(file.path)
            for file in files.iterator():
                project.size += mediaFileSizes(file)[0]
            logger.info(f"Updating {project.name}: Num files = {project.num_files}, Size = {project.size}")
            project.save()

def waitForMigrations():
    """Sleeps until database objects can be accessed.
    """
    while True:
        try:
            list(Project.objects.all())
            break
        except:
            time.sleep(10)

def buildSearchIndices(project_number, section, mode='index'):
    """ Builds search index for a project.
        section must be one of:
        'index' - create the index for the project if it does not exist
        'mappings' - create mappings for the project if they do not exist
        'media' - create documents for media
        'states' - create documents for states
        'localizations' - create documents for localizations
        'treeleaves' - create documents for treeleaves
    """
    project_name = Project.objects.get(pk=project_number).name
    logger.info(f"Building search indices for project {project_number}: {project_name}")

    if section == 'index':
        # Create indices
        logger.info("Building index...")
        TatorSearch().create_index(project_number)
        logger.info("Build index complete!")
        return

    if section == 'mappings':
        # Create mappings
        logger.info("Building mappings for media types...")
        for type_ in progressbar(list(MediaType.objects.filter(project=project_number))):
            TatorSearch().create_mapping(type_)
        logger.info("Building mappings for localization types...")
        for type_ in progressbar(list(LocalizationType.objects.filter(project=project_number))):
            TatorSearch().create_mapping(type_)
        logger.info("Building mappings for state types...")
        for type_ in progressbar(list(StateType.objects.filter(project=project_number))):
            TatorSearch().create_mapping(type_)
        logger.info("Building mappings for leaf types...")
        for type_ in progressbar(list(LeafType.objects.filter(project=project_number))):
            TatorSearch().create_mapping(type_)
        logger.info("Build mappings complete!")
        return

    class DeferredCall:
        def __init__(self, qs):
            self._qs = qs
        def __call__(self):
            for entity in self._qs.iterator():
                for doc in TatorSearch().build_document(entity, mode):
                    yield doc

    if section == 'media':
        # Create media documents
        logger.info("Building media documents...")
        qs = Media.objects.filter(project=project_number)

    if section == 'localizations':
        # Create localization documents
        logger.info("Building localization documents")
        qs = Localization.objects.filter(project=project_number)

    if section == 'states':
        # Create state documents
        logger.info("Building state documents...")
        qs = State.objects.filter(project=project_number)

    if section == 'treeleaves':
        # Create treeleaf documents
        logger.info("Building tree leaf documents...")
        qs = Leaf.objects.filter(project=project_number)

    batch_size = 500
    count = 0
    bar = ProgressBar(redirect_stderr=True, redirect_stdout=True)
    dc = DeferredCall(qs)
    total = qs.count()
    bar.start(max_value=total)
    for ok, result in streaming_bulk(TatorSearch().es, dc(),chunk_size=batch_size, raise_on_error=False):
        action, result = result.popitem()
        if not ok:
            print(f"Failed to {action} document! {result}")
        bar.update(min(count, total))
        count += 1
        if count > total:
            print(f"Count exceeds list size by {total - count}")
    bar.finish()

def makeDefaultVersion(project_number):
    """ Creates a default version for a project and sets all localizations
        and states to that version. Meant for usage on projects that were
        not previously using versions.
    """
    project = Project.objects.get(pk=project_number)
    version = Version.objects.filter(project=project, number=0)
    if version.exists():
        version = version[0]
    else:
        version = make_default_version(project)
    logger.info("Updating localizations...")
    qs = Localization.objects.filter(project=project)
    qs.update(version=version)
    logger.info("Updating states...")
    qs = State.objects.filter(project=project)
    qs.update(version=version)

def clearStaleProgress(project, ptype):
    from redis import Redis
    if ptype not in ['upload', 'algorithm', 'transcode']:
        print("Unknown progress type")

    Redis(host=os.getenv('REDIS_HOST')).delete(f'{ptype}_latest_{project}')

from pprint import pprint

def make_video_definition(disk_file, url_path):
        cmd = [
            "ffprobe",
            "-v","error",
            "-show_entries", "stream",
            "-print_format", "json",
            disk_file,
        ]
        output = subprocess.run(cmd, stdout=subprocess.PIPE, check=True).stdout
        video_info = json.loads(output)
        stream_idx=0
        for idx, stream in enumerate(video_info["streams"]):
            if stream["codec_type"] == "video":
                stream_idx = idx
                break
        stream = video_info["streams"][stream_idx]
        video_def = getVideoDefinition(
            url_path,
            stream["codec_name"],
            (stream["height"], stream["width"]),
            codec_description=stream["codec_long_name"])

        return video_def

def migrateVideosToNewSchema(project):
    videos = Media.objects.filter(project=project, meta__dtype='video')
    for video in progressbar(videos):
        streaming_definition = make_video_definition(
            os.path.join(settings.MEDIA_ROOT,
                         video.file.name),
            os.path.join(settings.MEDIA_URL,
                         video.file.name))
        if video.segment_info:
            streaming_definition['segment_info'] = video.segment_info
        if video.original:
            archival_definition = make_video_definition(video.original,
                                                        video.original)
        media_files = {"streaming": [streaming_definition]}

        if archival_definition:
            media_files.update({"archival": [archival_definition]})
        video.media_files = media_files
        pprint(media_files)
        video.save()

def fixVideoDims(project):
    videos = Media.objects.filter(project=project, meta__dtype='video')
    for video in progressbar(videos):
        try:
            if video.original:
                archival_definition = make_video_definition(video.original,
                                                            video.original)
                video.height = archival_definition["resolution"][0]
                video.width = archival_definition["resolution"][1]
                video.save()
        except:
            print(f"Error on {video.pk}")

def clearOldFilebeatIndices():
    es = Elasticsearch([os.getenv('ELASTICSEARCH_HOST')])
    for index in es.indices.get('filebeat-*'):
        tokens = str(index).split('-')
        if len(tokens) < 3:
            continue
        dt = parse(tokens[2])
        delta = datetime.datetime.now() - dt
        if delta.days > 7:
            logger.info(f"Deleting old filebeat index {index}")
            es.indices.delete(str(index))

def cleanup_uploads(max_age_days=1):
    """ Removes uploads that are greater than a day old.
    """
    upload_paths = [settings.UPLOAD_ROOT]
    upload_shards = os.getenv('UPLOAD_SHARDS')
    if upload_shards is not None:
        upload_paths += [f'/{shard}' for shard in upload_shards.split(',')]
    now = time.time()
    for path in upload_paths:
        num_removed = 0
        for root, dirs, files in os.walk(path):
            for f in files:
                file_path = os.path.join(root, f)
                not_resource = Resource.objects.filter(path=file_path).count() == 0
                if (os.stat(file_path).st_mtime < now - 86400 * max_age_days) and not_resource:
                    os.remove(file_path)
                    num_removed += 1
        logger.info(f"Deleted {num_removed} files from {path} that were > {max_age_days} days old...")
    logger.info("Cleanup finished!")

def make_sections():
    for project in Project.objects.all().iterator():
        es = Elasticsearch([os.getenv('ELASTICSEARCH_HOST')])
        result = es.search(index=f'project_{project.pk}',
                           body={'size': 0,
                                 'aggs': {'sections': {'terms': {'field': 'tator_user_sections',
                                                                 'size': 1000}}}},
                           stored_fields=[])
        for section in result['aggregations']['sections']['buckets']:
            Section.objects.create(project=project,
                                   name=section['key'],
                                   tator_user_sections=section['key'])
            logger.info(f"Created section {section['key']} in project {project.pk}!")

def make_resources():

    # Function to build resource objects from paths.
    def _resources_from_paths(paths):
        paths = [os.readlink(path) if os.path.islink(path) else path for path in paths]
        exists = list(Resource.objects.filter(path__in=paths).values_list('path', flat=True))
        needs_create = list(set(paths).difference(exists))
        paths = []
        return [Resource(path=p) for p in needs_create]

    # Function to get paths from media.
    def _paths_from_media(media):
        paths = []
        if media.file:
            paths.append(media.file.path)
        if media.media_files:
            if 'audio' in media.media_files:
                paths += [f['path'] for f in media.media_files['audio']]
            if 'streaming' in media.media_files:
                paths += [f['path'] for f in media.media_files['streaming']]
                paths += [f['segment_info'] for f in media.media_files['streaming']]
            if 'archival' in media.media_files:
                paths += [f['path'] for f in media.media_files['archival']]
        if media.original:
            paths.append(media.original)
        return paths

    # Create all resource objects that don't already exist.
    num_resources = 0
    path_list = []
    create_buffer = []
    for media in Media.objects.all().iterator():
        path_list += _paths_from_media(media)
        if len(path_list) > 1000:
            create_buffer += _resources_from_paths(path_list)
            path_list = []
        if len(create_buffer) > 1000:
            Resource.objects.bulk_create(create_buffer)
            num_resources += len(create_buffer)
            create_buffer = []
            logger.info(f"Created {num_resources} resources...")
    if path_list:
        create_buffer += _resources_from_paths(path_list)
        path_list = []
    if create_buffer:
        Resource.objects.bulk_create(create_buffer)
        num_resources += len(create_buffer)
        create_buffer = []
        logger.info(f"Created {num_resources} resources...")
    logger.info("Resource creation complete!")

    # Create many to many relations.
    Resource.media.through.objects.all().delete()
    num_relations = 0
    media_relations = []
    for media in Media.objects.all().iterator():
        path_list = _paths_from_media(media)
        path_list = [os.readlink(path) if os.path.islink(path) else path for path in path_list]
        for resource in Resource.objects.filter(path__in=path_list).iterator():
            media_relation = Resource.media.through(
                resource_id=resource.id,
                media_id=media.id,
            )
            media_relations.append(media_relation)
        if len(media_relations) > 1000:
            Resource.media.through.objects.bulk_create(media_relations)
            num_relations += len(media_relations)
            media_relations = []
            logger.info(f"Created {num_relations} media relations...")
    if media_relations:
        Resource.media.through.objects.bulk_create(media_relations)
        num_relations += len(media_relations)
        media_relations = []
        logger.info(f"Created {num_relations} media relations...")
    logger.info("Media relation creation complete!")

