import os

from django.contrib.gis.db.models import Model
from django.contrib.gis.db.models import ForeignKey
from django.contrib.gis.db.models import ManyToManyField
from django.contrib.gis.db.models import CharField
from django.contrib.gis.db.models import TextField
from django.contrib.gis.db.models import URLField
from django.contrib.gis.db.models import SlugField
from django.contrib.gis.db.models import BooleanField
from django.contrib.gis.db.models import IntegerField
from django.contrib.gis.db.models import BigIntegerField
from django.contrib.gis.db.models import PositiveIntegerField
from django.contrib.gis.db.models import FloatField
from django.contrib.gis.db.models import DateTimeField
from django.contrib.gis.db.models import PointField
from django.contrib.gis.db.models import FileField
from django.contrib.gis.db.models import FilePathField
from django.contrib.gis.db.models import ImageField
from django.contrib.gis.db.models import PROTECT
from django.contrib.gis.db.models import CASCADE
from django.contrib.gis.db.models import SET_NULL
from django.contrib.gis.geos import Point
from django.contrib.auth.models import AbstractUser
from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.fields import JSONField
from django.core.validators import MinValueValidator
from django.core.validators import RegexValidator
from django.db.models import FloatField, Transform
from django.db.models.signals import post_save
from django.db.models.signals import pre_delete
from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from django.conf import settings
from polymorphic.models import PolymorphicModel
from enumfields import Enum
from enumfields import EnumField
from django_ltree.fields import PathField

from .cache import TatorCache
from .search import TatorSearch

from collections import UserDict

import pytz
import datetime
import logging
import os
import shutil
import uuid

# Load the main.view logger
logger = logging.getLogger(__name__)

class Depth(Transform):
    lookup_name = "depth"
    function = "nlevel"

    @property
    def output_field(self):
        return IntegerField()

PathField.register_lookup(Depth)

FileFormat= [('mp4','mp4'), ('webm','webm'), ('mov', 'mov')]
ImageFileFormat= [('jpg','jpg'), ('png','png'), ('bmp', 'bmp'), ('raw', 'raw')]

## Describes different association models in the database
AssociationTypes = [('Media','Relates to one or more media items'),
                    ('Frame', 'Relates to a specific frame in a video'), #Relates to one or more frames in a video
                    ('Localization', 'Relates to localization(s)')] #Relates to one-to-many localizations

class MediaAccess(Enum):
    VIEWABLE = 'viewable'
    DOWNLOADABLE = 'downloadable'
    ARCHIVAL = 'archival'
    REMOVE = 'remove'

class Marker(Enum):
    NONE = 'none'
    CROSSHAIR = 'crosshair'
    SQUARE = 'square'
    CIRCLE = 'circle'

class InterpolationMethods(Enum):
    NONE = 'none'
    LATEST = 'latest'
    NEAREST = 'nearest'
    LINEAR = 'linear'
    SPLINE = 'spline'

class JobResult(Enum):
    FINISHED = 'finished'
    FAILED = 'failed'

class JobStatus(Enum): # Keeping for migration compatiblity
    pass

class JobChannel(Enum): # Keeping for migration compatiblity
    pass

class Permission(Enum):
    VIEW_ONLY = 'r'
    CAN_EDIT = 'w'
    CAN_TRANSFER = 't'
    CAN_EXECUTE = 'x'
    FULL_CONTROL = 'a'

class HistogramPlotType(Enum):
    PIE = 'pie'
    BAR = 'bar'

class TwoDPlotType(Enum):
    LINE = 'line'
    SCATTER = 'scatter'

class Organization(Model):
    name = CharField(max_length=128)
    def __str__(self):
        return self.name

class User(AbstractUser):
    middle_initial = CharField(max_length=1)
    initials = CharField(max_length=3)
    organization = ForeignKey(Organization, on_delete=SET_NULL, null=True, blank=True)
    last_login = DateTimeField(null=True, blank=True)
    last_failed_login = DateTimeField(null=True, blank=True)
    failed_login_count = IntegerField(default=0)

    def __str__(self):
        if self.first_name or self.last_name:
            return f"{self.first_name} {self.last_name}"
        else:
            return "---"

def delete_polymorphic_qs(qs):
    """Deletes a polymorphic queryset.
    """
    types = set(map(lambda x: type(x), qs))
    ids = list(map(lambda x: x.id, list(qs)))
    for entity_type in types:
        qs = entity_type.objects.filter(pk__in=ids)
        qs.delete()

class Project(Model):
    name = CharField(max_length=128)
    creator = ForeignKey(User, on_delete=PROTECT, related_name='creator')
    created = DateTimeField(auto_now_add=True)
    size = BigIntegerField(default=0)
    """Size of all media in project in bytes.
    """
    num_files = IntegerField(default=0)
    summary = CharField(max_length=1024)
    filter_autocomplete = JSONField(null=True, blank=True)
    section_order = ArrayField(CharField(max_length=128), default=list)
    def has_user(self, user_id):
        return self.membership_set.filter(user_id=user_id).exists()
    def user_permission(self, user_id):
        permission = None
        qs = self.membership_set.filter(user_id=user_id)
        if qs.exists():
            permission = qs[0].permission
        return permission
    def __str__(self):
        return self.name

    def delete(self, *args, **kwargs):
        # Delete attribute types
        qs = AttributeTypeBase.objects.filter(project=self)
        delete_polymorphic_qs(qs)
        # Delete entities
        qs = EntityBase.objects.filter(project=self)
        delete_polymorphic_qs(qs)
        # Delete entity types
        qs = EntityTypeBase.objects.filter(project=self)
        delete_polymorphic_qs(qs)
        super().delete(*args, **kwargs)

class Version(Model):
    name = CharField(max_length=128)
    description = CharField(max_length=1024, blank=True)
    number = PositiveIntegerField()
    project = ForeignKey(Project, on_delete=CASCADE)
    created_datetime = DateTimeField(auto_now_add=True, null=True, blank=True)
    created_by = ForeignKey(User, on_delete=SET_NULL, null=True, blank=True, related_name='version_created_by')
    show_empty = BooleanField(default=False)
    """ Tells the UI to show this version even if the current media does not
        have any annotations.
    """

    def __str__(self):
        out = f"{self.name}"
        if self.description:
            out += f" | {self.description}"
        return out

def make_default_version(instance):
    return Version.objects.create(
        name="Baseline",
        description="Initial version",
        project=instance,
        number=0,
    )

@receiver(post_save, sender=Project)
def project_save(sender, instance, created, **kwargs):
    TatorCache().invalidate_project_cache(instance.pk)
    TatorSearch().create_index(instance.pk)
    if created:
        make_default_version(instance)

@receiver(pre_delete, sender=Project)
def delete_index_project(sender, instance, **kwargs):
    TatorSearch().delete_index(instance.pk)

class Membership(Model):
    """Stores a user and their access level for a project.
    """
    project = ForeignKey(Project, on_delete=CASCADE)
    user = ForeignKey(User, on_delete=CASCADE)
    permission = EnumField(Permission, max_length=1, default=Permission.CAN_EDIT)
    def __str__(self):
        return f'{self.user} | {self.permission} | {self.project}'

# Entity types

class MediaType(Model):
    dtype = CharField(max_length=16, choices=[('image', 'image'), ('video', 'video')])
    project = ForeignKey(Project, on_delete=CASCADE, null=True, blank=True)
    name = CharField(max_length=64)
    description = CharField(max_length=256, blank=True)
    editTriggers = JSONField(null=True,
                             blank=True)
    file_format = CharField(max_length=4,
                            null=True,
                            blank=True,
                            default=None)
    keep_original = BooleanField(default=True)
    attribute_types = JSONField()
    def __str__(self):
        return f'{self.name} | {self.project}'

class LocalizationType(Model):
    dtype = CharField(max_length=16,
                      choices=[('box', 'box'), ('line', 'line'), ('dot', 'dot')])
    project = ForeignKey(Project, on_delete=CASCADE, null=True, blank=True)
    name = CharField(max_length=64)
    description = CharField(max_length=256, blank=True)
    media = ManyToManyField(MediaType)
    bounded = BooleanField(default=True)
    colorMap = JSONField(null=True, blank=True)
    attribute_types = JSONField()
    def __str__(self):
        return f'{self.name} | {self.project}'

class StateType(Model):
    dtype = 'state'
    project = ForeignKey(Project, on_delete=CASCADE, null=True, blank=True)
    name = CharField(max_length=64)
    description = CharField(max_length=256, blank=True)
    media = ManyToManyField(MediaType)
    markers = BooleanField(default=False)
    interpolation = EnumField(
        InterpolationMethods,
        default=InterpolationMethods.NONE
    )
    association = CharField(max_length=64,
                            choices=AssociationTypes,
                            default=AssociationTypes[0][0])
    attribute_types = JSONField()
    def __str__(self):
        return f'{self.name} | {self.project}'

class LeafType(Model):
    project = ForeignKey(Project, on_delete=CASCADE, null=True, blank=True)
    name = CharField(max_length=64)
    description = CharField(max_length=256, blank=True)
    def __str__(self):
        return f'{self.name} | {self.project}'

# Entities (stores actual data)

class Media(Model):
    """
    Fields:

    original: Originally uploaded file. Users cannot interact with it except
              by downloading it.

              .. deprecated :: Use media_files object

    segment_info: File for segment files to support MSE playback.

                  .. deprecated :: Use meda_files instead

    media_files: Dictionary to contain a map of all files for this media.
                 The schema looks like this:

                 .. code-block ::

                     map = {"archival": [ VIDEO_DEF, VIDEO_DEF,... ],
                            "streaming": [ VIDEO_DEF, VIDEO_DEF, ... ]}
                     video_def = {"path": <path_to_disk>,
                                  "codec": <human readable codec>,
                                  "resolution": [<vertical pixel count, e.g. 720>, width]


                                  ###################
                                  # Optional Fields #
                                  ###################

                                  # Path to the segments.json file for streaming files.
                                  # not expected/required for archival. Required for
                                  # MSE playback with seek support for streaming files.
                                  segment_info = <path_to_json>

                                  # If supplied will use this instead of currently
                                  # connected host. e.g. https://example.com
                                  "host": <host url>
                                  # If specified will be used for HTTP authorization
                                  # in the request for media. I.e. "bearer <token>"
                                  "http_auth": <http auth header>

                                  # Example mime: 'video/mp4; codecs="avc1.64001e"'
                                  # Only relevant for straming files, will assume
                                  # example above if not present.
                                  "codec_mime": <mime for MSE decode>

                                  "codec_description": <description other than codec>}


    """
    project = ForeignKey(Project, on_delete=CASCADE, null=True, blank=True)
    meta = ForeignKey(MediaType, on_delete=CASCADE)
    """ Meta points to the defintion of the attribute field. That is
        a handful of AttributeTypes are associated to a given MediaType
        that is pointed to by this value. That set describes the `attribute`
        field of this structure. """
    attributes = JSONField(null=True, blank=True)
    created_datetime = DateTimeField(auto_now_add=True, null=True, blank=True)
    created_by = ForeignKey(User, on_delete=SET_NULL, null=True, blank=True, related_name='created_by')
    modified_datetime = DateTimeField(auto_now=True, null=True, blank=True)
    modified_by = ForeignKey(User, on_delete=SET_NULL, null=True, blank=True, related_name='modified_by')
    name = CharField(max_length=256)
    md5 = SlugField(max_length=32)
    """ md5 hash of the originally uploaded file. """
    file = FileField()
    last_edit_start = DateTimeField(null=True, blank=True)
    """ Start datetime of a session in which the media's annotations were edited.
    """
    last_edit_end = DateTimeField(null=True, blank=True)
    """ End datetime of a session in which the media's annotations were edited.
    """
    original = FilePathField(path=settings.RAW_ROOT, null=True, blank=True)
    thumbnail = ImageField()
    thumbnail_gif = ImageField()
    num_frames = IntegerField(null=True)
    fps = FloatField(null=True)
    codec = CharField(null=True,max_length=256)
    width=IntegerField(null=True)
    height=IntegerField(null=True)
    segment_info = FilePathField(path=settings.MEDIA_ROOT, null=True,
                                 blank=True)
    media_files = JSONField(null=True, blank=True)

@receiver(post_save, sender=Media)
def media_save(sender, instance, created, **kwargs):
    TatorCache().invalidate_media_list_cache(instance.project.pk)
    TatorSearch().create_document(instance)

def safe_delete(path):
    try:
        logger.info(f"Deleting {path}")
        os.remove(path)
    except:
        logger.warning(f"Could not remove {path}")

@receiver(pre_delete, sender=Media)
def media_delete(sender, instance, **kwargs):
    TatorCache().invalidate_media_list_cache(instance.project.pk)
    TatorSearch().delete_document(instance)
    instance.file.delete(False)
    if instance.original != None:
        path = str(instance.original)
        safe_delete(path)

class Localization(Model):
    project = ForeignKey(Project, on_delete=CASCADE, null=True, blank=True)
    meta = ForeignKey(LocalizationType, on_delete=CASCADE)
    """ Meta points to the defintion of the attribute field. That is
        a handful of AttributeTypes are associated to a given LocalizationType
        that is pointed to by this value. That set describes the `attribute`
        field of this structure. """
    attributes = JSONField(null=True, blank=True)
    created_datetime = DateTimeField(auto_now_add=True, null=True, blank=True)
    created_by = ForeignKey(User, on_delete=SET_NULL, null=True, blank=True, related_name='created_by')
    modified_datetime = DateTimeField(auto_now=True, null=True, blank=True)
    modified_by = ForeignKey(User, on_delete=SET_NULL, null=True, blank=True, related_name='modified_by')
    user = ForeignKey(User, on_delete=PROTECT)
    media = ForeignKey(EntityMediaBase, on_delete=CASCADE)
    frame = PositiveIntegerField(null=True)
    thumbnail_image = ForeignKey(EntityMediaImage, on_delete=SET_NULL,
                                 null=True,blank=True,
                                 related_name='thumbnail_image')
    version = ForeignKey(Version, on_delete=CASCADE, null=True, blank=True)
    modified = BooleanField(null=True, blank=True)
    """ Indicates whether an annotation is original or modified.
        null: Original upload, no modifications.
        false: Original upload, but was modified or deleted.
        true: Modified since upload or created via web interface.
    """
    x = FloatField()
    y = FloatField()
    x0 = FloatField()
    y0 = FloatField()
    x1 = FloatField()
    y1 = FloatField()
    width = FloatField()
    height = FloatField()

@receiver(post_save, sender=Localization)
def localization_save(sender, instance, created, **kwargs):
    TatorCache().invalidate_localization_list_cache(instance.media.pk, instance.meta.pk)
    if getattr(instance,'_inhibit', False) == False:
        TatorSearch().create_document(instance)
    else:
        pass

@receiver(pre_delete, sender=Localization)
def localization_delete(sender, instance, **kwargs):
    TatorCache().invalidate_localization_list_cache(instance.media.pk, instance.meta.pk)
    TatorSearch().delete_document(instance)
    if instance.thumbnail_image:
        instance.thumbnail_image.delete()

class Association(Model):
    media = ManyToManyField(Media)
    localizations = ManyToManyField(Localization)
    segments = JSONField(null=True)
    color = CharField(null=True,blank=True,max_length=8)
    frame = PositiveIntegerField()
    extracted = ForeignKey(Media,
                           on_delete=SET_NULL,
                           null=True,
                           blank=True)
    def states(media_id):
        associations = Association.objects.filter(media__in=media_id)
        localizations = Localization.objects.filter(media__in=media_id)
        associations.union(Association.objects.filter(localizations__in=localizations)
        return State.objects.filter(association__in=list(associations))

class State(Model):
    """
    A State is an event that occurs, potentially independent, from that of
    a media element. It is associated with 0 (1 to be useful) or more media
    elements. If a frame is supplied it was collected at that time point.
    """
    project = ForeignKey(Project, on_delete=CASCADE, null=True, blank=True)
    meta = ForeignKey(EntityTypeBase, on_delete=CASCADE)
    """ Meta points to the defintion of the attribute field. That is
        a handful of AttributeTypes are associated to a given EntityType
        that is pointed to by this value. That set describes the `attribute`
        field of this structure. """
    attributes = JSONField(null=True, blank=True)
    created_datetime = DateTimeField(auto_now_add=True, null=True, blank=True)
    created_by = ForeignKey(User, on_delete=SET_NULL, null=True, blank=True, related_name='created_by')
    modified_datetime = DateTimeField(auto_now=True, null=True, blank=True)
    modified_by = ForeignKey(User, on_delete=SET_NULL, null=True, blank=True, related_name='modified_by')
    association = ForeignKey(Association, on_delete=CASCADE)
    version = ForeignKey(Version, on_delete=CASCADE, null=True, blank=True)
    modified = BooleanField(null=True, blank=True)
    """ Indicates whether an annotation is original or modified.
        null: Original upload, no modifications.
        false: Original upload, but was modified or deleted.
        true: Modified since upload or created via web interface.
    """
    def selectOnMedia(media_id):
        return Association.states(media_id)

@receiver(post_save, sender=State)
def state_save(sender, instance, created, **kwargs):
    TatorSearch().create_document(instance)

@receiver(pre_delete, sender=State)
def state_delete(sender, instance, **kwargs):
    TatorSearch().delete_document(instance)

class Leaf(Model):
    project = ForeignKey(Project, on_delete=CASCADE, null=True, blank=True)
    meta = ForeignKey(EntityTypeBase, on_delete=CASCADE)
    """ Meta points to the defintion of the attribute field. That is
        a handful of AttributeTypes are associated to a given EntityType
        that is pointed to by this value. That set describes the `attribute`
        field of this structure. """
    attributes = JSONField(null=True, blank=True)
    created_datetime = DateTimeField(auto_now_add=True, null=True, blank=True)
    created_by = ForeignKey(User, on_delete=SET_NULL, null=True, blank=True, related_name='created_by')
    modified_datetime = DateTimeField(auto_now=True, null=True, blank=True)
    modified_by = ForeignKey(User, on_delete=SET_NULL, null=True, blank=True, related_name='modified_by')
    parent=ForeignKey('self', on_delete=SET_NULL, blank=True, null=True)
    path=PathField(unique=True)
    name = CharField(max_length=255)

    class Meta:
        verbose_name_plural = "Leaves"

    def __str__(self):
        return str(self.path)

    def depth(self):
        return Leaf.objects.annotate(depth=Depth('path')).get(pk=self.pk).depth

    def subcategories(self, minLevel=1):
        return Leaf.objects.select_related('parent').filter(
            path__descendants=self.path,
            path__depth__gte=self.depth()+minLevel
        )

    def computePath(self):
        """ Returns the string representing the path element """
        pathStr=self.name.replace(" ","_").replace("-","_").replace("(","_").replace(")","_")
        if self.parent:
            pathStr=self.parent.computePath()+"."+pathStr
        elif self.project:
            projName=self.project.name.replace(" ","_").replace("-","_").replace("(","_").replace(")","_")
            pathStr=projName+"."+pathStr
        return pathStr

@receiver(post_save, sender=Leaf)
def leaf_save(sender, instance, **kwargs):
    for ancestor in instance.computePath().split('.'):
        TatorCache().invalidate_treeleaf_list_cache(ancestor)
    TatorSearch().create_document(instance)

@receiver(pre_delete, sender=Leaf)
def leaf_delete(sender, instance, **kwargs):
    for ancestor in instance.computePath().split('.'):
        TatorCache().invalidate_treeleaf_list_cache(ancestor)
    TatorSearch().delete_document(instance)

class Analysis(Model):
    project = ForeignKey(Project, on_delete=CASCADE)
    name = CharField(max_length=64)
    data_query = CharField(max_length=1024, default='*')

class EntityTypeBase(PolymorphicModel):
    project = ForeignKey(Project, on_delete=CASCADE, null=True, blank=True)
    name = CharField(max_length=64)
    description = CharField(max_length=256, blank=True)
    visible=BooleanField(default=True)
    def __str__(self):
        return f'{self.name} | {self.project}'

class EntityTypeMediaBase(EntityTypeBase):
    uploadable = BooleanField(default=True)
    editTriggers = JSONField(null=True,
                             blank=True)

class EntityTypeMediaImage(EntityTypeMediaBase):
    entity_name = 'Image'
    dtype = 'image'
    file_format = CharField(max_length=4,
                            null=True,
                            blank=True,
                            choices=ImageFileFormat,
                            default=None)

class EntityTypeMediaVideo(EntityTypeMediaBase):
    entity_name = 'Video'
    dtype = 'video'
    file_format = CharField(max_length=4,
                            null=True,
                            blank=True,
                            choices=FileFormat,
                            default=None)
    keep_original = BooleanField(default=True)

class EntityTypeLocalizationBase(EntityTypeBase):
    media = ManyToManyField(EntityTypeMediaBase)
    bounded = BooleanField(default=True)
    colorMap = JSONField(null=True, blank=True)

class EntityTypeLocalizationDot(EntityTypeLocalizationBase):
    entity_name = 'Dot'
    dtype = 'dot'
    marker = EnumField(Marker, max_length=9, default=Marker.CIRCLE)
    marker_size = PositiveIntegerField(default=12)

class EntityTypeLocalizationLine(EntityTypeLocalizationBase):
    entity_name = 'Line'
    dtype = 'line'
    line_width = PositiveIntegerField(default=3)

class EntityTypeLocalizationBox(EntityTypeLocalizationBase):
    entity_name = 'Box'
    dtype = 'box'
    line_width = PositiveIntegerField(default=3)

class EntityTypeState(EntityTypeBase):
    """ Used to conglomerate AttributeTypes into a set """
    entity_name = 'State'
    dtype = 'state'
    media = ManyToManyField(EntityTypeMediaBase)
    markers = BooleanField(default=False)
    interpolation = EnumField(
        InterpolationMethods,
        default=InterpolationMethods.NONE
    )
    association = CharField(max_length=64,
                            choices=AssociationTypes,
                            default=AssociationTypes[0][0])

class EntityTypeTreeLeaf(EntityTypeBase):
    entity_name = 'TreeLeaf'
    dtype = 'treeleaf'

# Entities (stores actual data)

class EntityBase(PolymorphicModel):
    project = ForeignKey(Project, on_delete=CASCADE, null=True, blank=True)
    meta = ForeignKey(EntityTypeBase, on_delete=CASCADE)
    """ Meta points to the defintion of the attribute field. That is
        a handful of AttributeTypes are associated to a given EntityType
        that is pointed to by this value. That set describes the `attribute`
        field of this structure. """
    attributes = JSONField(null=True, blank=True)
    created_datetime = DateTimeField(auto_now_add=True, null=True, blank=True)
    created_by = ForeignKey(User, on_delete=SET_NULL, null=True, blank=True, related_name='created_by')
    modified_datetime = DateTimeField(auto_now=True, null=True, blank=True)
    modified_by = ForeignKey(User, on_delete=SET_NULL, null=True, blank=True, related_name='modified_by')

class EntityMediaBase(EntityBase):
    name = CharField(max_length=256)
    uploader = ForeignKey(User, on_delete=PROTECT)
    upload_datetime = DateTimeField()
    md5 = SlugField(max_length=32)
    """ md5 hash of the originally uploaded file. """
    file = FileField()
    last_edit_start = DateTimeField(null=True, blank=True)
    """ Start datetime of a session in which the media's annotations were edited.
    """
    last_edit_end = DateTimeField(null=True, blank=True)
    """ End datetime of a session in which the media's annotations were edited.
    """

@receiver(post_save, sender=EntityMediaBase)
def media_save(sender, instance, created, **kwargs):
    TatorSearch().create_document(instance)

@receiver(pre_delete, sender=EntityMediaBase)
def media_delete(sender, instance, **kwargs):
    TatorSearch().delete_document(instance)

class EntityMediaImage(EntityMediaBase):
    thumbnail = ImageField()
    width=IntegerField(null=True)
    height=IntegerField(null=True)

@receiver(post_save, sender=EntityMediaImage)
def image_save(sender, instance, created, **kwargs):
    TatorCache().invalidate_media_list_cache(instance.project.pk)
    TatorSearch().create_document(instance)

@receiver(pre_delete, sender=EntityMediaImage)
def image_delete(sender, instance, **kwargs):
    TatorCache().invalidate_media_list_cache(instance.project.pk)
    TatorSearch().delete_document(instance)
    instance.file.delete(False)
    instance.thumbnail.delete(False)

def getVideoDefinition(path, codec, resolution, **kwargs):
    """ Convenience function to generate video definiton dictionary """
    obj = {"path": path,
           "codec": codec,
           "resolution": resolution}
    for arg in kwargs:
        if arg in ["segment_info",
                   "host",
                   "http_auth",
                   "codec_meme",
                   "codec_description"]:
            obj[arg] = kwargs[arg]
        else:
            raise TypeError(f"Invalid argument '{arg}' supplied")
    return obj

class EntityMediaVideo(EntityMediaBase):
    """
    Fields:

    original: Originally uploaded file. Users cannot interact with it except
              by downloading it.

              .. deprecated :: Use media_files object

    segment_info: File for segment files to support MSE playback.

                  .. deprecated :: Use meda_files instead

    media_files: Dictionary to contain a map of all files for this media.
                 The schema looks like this:

                 .. code-block ::

                     map = {"archival": [ VIDEO_DEF, VIDEO_DEF,... ],
                            "streaming": [ VIDEO_DEF, VIDEO_DEF, ... ]}
                     video_def = {"path": <path_to_disk>,
                                  "codec": <human readable codec>,
                                  "resolution": [<vertical pixel count, e.g. 720>, width]


                                  ###################
                                  # Optional Fields #
                                  ###################

                                  # Path to the segments.json file for streaming files.
                                  # not expected/required for archival. Required for
                                  # MSE playback with seek support for streaming files.
                                  segment_info = <path_to_json>

                                  # If supplied will use this instead of currently
                                  # connected host. e.g. https://example.com
                                  "host": <host url>
                                  # If specified will be used for HTTP authorization
                                  # in the request for media. I.e. "bearer <token>"
                                  "http_auth": <http auth header>

                                  # Example mime: 'video/mp4; codecs="avc1.64001e"'
                                  # Only relevant for straming files, will assume
                                  # example above if not present.
                                  "codec_mime": <mime for MSE decode>

                                  "codec_description": <description other than codec>}


    """
    original = FilePathField(path=settings.RAW_ROOT, null=True, blank=True)
    thumbnail = ImageField()
    thumbnail_gif = ImageField()
    num_frames = IntegerField(null=True)
    fps = FloatField(null=True)
    codec = CharField(null=True,max_length=256)
    width=IntegerField(null=True)
    height=IntegerField(null=True)
    segment_info = FilePathField(path=settings.MEDIA_ROOT, null=True,
                                 blank=True)
    media_files = JSONField(null=True, blank=True)

@receiver(post_save, sender=EntityMediaVideo)
def video_save(sender, instance, created, **kwargs):
    TatorCache().invalidate_media_list_cache(instance.project.pk)
    TatorSearch().create_document(instance)

def safe_delete(path):
    try:
        logger.info(f"Deleting {path}")
        os.remove(path)
    except:
        logger.warning(f"Could not remove {path}")

@receiver(pre_delete, sender=EntityMediaVideo)
def video_delete(sender, instance, **kwargs):
    TatorCache().invalidate_media_list_cache(instance.project.pk)
    TatorSearch().delete_document(instance)
    instance.file.delete(False)
    if instance.original != None:
        path = str(instance.original)
        safe_delete(path)

    # Delete all the files referenced in media_files
    if not instance.media_files is None:
        files = instance.media_files.get('streaming', [])
        for obj in files:
            path = "/data" + obj['path']
            safe_delete(path)
            path = "/data" + obj['segment_info']
            safe_delete(path)
        files = instance.media_files.get('archival', [])
        for obj in files:
            safe_delete(obj['path'])
    instance.thumbnail.delete(False)
    instance.thumbnail_gif.delete(False)

class EntityLocalizationBase(EntityBase):
    user = ForeignKey(User, on_delete=PROTECT)
    media = ForeignKey(EntityMediaBase, on_delete=CASCADE)
    frame = PositiveIntegerField(null=True)
    thumbnail_image = ForeignKey(EntityMediaImage, on_delete=SET_NULL,
                                 null=True,blank=True,
                                 related_name='thumbnail_image')
    version = ForeignKey(Version, on_delete=CASCADE, null=True, blank=True)
    modified = BooleanField(null=True, blank=True)
    """ Indicates whether an annotation is original or modified.
        null: Original upload, no modifications.
        false: Original upload, but was modified or deleted.
        true: Modified since upload or created via web interface.
    """

    def selectOnMedia(media_id):
        return EntityLocalizationBase.objects.filter(media=media_id)

@receiver(post_save, sender=EntityLocalizationBase)
def localization_save(sender, instance, created, **kwargs):
    if getattr(instance,'_inhibit', False) == False:
        TatorSearch().create_document(instance)
    else:
        pass

@receiver(pre_delete, sender=EntityLocalizationBase)
def localization_delete(sender, instance, **kwargs):
    """ Delete generated thumbnails if a localization box is deleted """
    TatorSearch().delete_document(instance)
    if instance.thumbnail_image:
        instance.thumbnail_image.delete()

class EntityLocalizationDot(EntityLocalizationBase):
    x = FloatField()
    y = FloatField()

@receiver(post_save, sender=EntityLocalizationDot)
def dot_save(sender, instance, created, **kwargs):
    TatorCache().invalidate_localization_list_cache(instance.media.pk, instance.meta.pk)
    if getattr(instance,'_inhibit', False) == False:
        TatorSearch().create_document(instance)
    else:
        pass

@receiver(pre_delete, sender=EntityLocalizationDot)
def dot_delete(sender, instance, **kwargs):
    TatorCache().invalidate_localization_list_cache(instance.media.pk, instance.meta.pk)
    TatorSearch().delete_document(instance)

class EntityLocalizationLine(EntityLocalizationBase):
    x0 = FloatField()
    y0 = FloatField()
    x1 = FloatField()
    y1 = FloatField()

@receiver(post_save, sender=EntityLocalizationLine)
def line_save(sender, instance, created, **kwargs):
    TatorCache().invalidate_localization_list_cache(instance.media.pk, instance.meta.pk)
    if getattr(instance,'_inhibit', False) == False:
        TatorSearch().create_document(instance)
    else:
        logger.info("Inhibited ES insertion")

@receiver(pre_delete, sender=EntityLocalizationLine)
def line_delete(sender, instance, **kwargs):
    TatorCache().invalidate_localization_list_cache(instance.media.pk, instance.meta.pk)
    TatorSearch().delete_document(instance)

class EntityLocalizationBox(EntityLocalizationBase):
    x = FloatField()
    y = FloatField()
    width = FloatField()
    height = FloatField()

@receiver(post_save, sender=EntityLocalizationBox)
def box_save(sender, instance, created, **kwargs):
    TatorCache().invalidate_localization_list_cache(instance.media.pk, instance.meta.pk)
    if getattr(instance,'_inhibit', False) == False:
        TatorSearch().create_document(instance)
    else:
        pass

@receiver(pre_delete, sender=EntityLocalizationBox)
def box_delete(sender, instance, **kwargs):
    TatorCache().invalidate_localization_list_cache(instance.media.pk, instance.meta.pk)
    TatorSearch().delete_document(instance)

class AssociationType(PolymorphicModel):
    media = ManyToManyField(EntityMediaBase)
    def states(media_ids):
        # Get localization associations
        localizationsForMedia=EntityLocalizationBase.objects.filter(media__in=media_ids)
        localizationAssociations=LocalizationAssociation.objects.filter(localizations__in=localizationsForMedia).distinct()
        # Downcast to base class
        ids = [loc.id for loc in localizationAssociations]
        localizationAssociations=AssociationType.objects.filter(pk__in=ids)
        # Get other associations (frame, media)
        associations=AssociationType.objects.filter(media__in=media_ids)
        associations = list(associations.union(localizationAssociations))
        # Get states with these associations
        states = EntityState.objects.filter(association__in=associations)
        return states


class MediaAssociation(AssociationType):
    def states(media_id):
        mediaAssociations=MediaAssociation.objects.filter(media__in=media_id)
        return EntityState.objects.filter(association__in=mediaAssociations)

class LocalizationAssociation(AssociationType):
    """
    color : "#RRGGBB" or "RRGGBB" to represent track color. If not set, display
            will use automatic color progression.
    """
    localizations = ManyToManyField(EntityLocalizationBase)
    segments = JSONField(null=True)
    color = CharField(null=True,blank=True,max_length=8)

    def states(media_id):
        localizationsForMedia=EntityLocalizationBase.objects.filter(media__in=media_id)
        localizationAssociations=LocalizationAssociation.objects.filter(localizations__in=localizationsForMedia).distinct()
        return EntityState.objects.filter(association__in=localizationAssociations)

@receiver(m2m_changed, sender=LocalizationAssociation.localizations.through)
def calcSegments(sender, **kwargs):
    instance=kwargs['instance']
    sortedLocalizations=EntityLocalizationBase.objects.filter(pk__in=instance.localizations.all()).order_by('frame')

    #Bring up related media to association
    instance.media.set(sortedLocalizations.all().values_list('media', flat=True))
    segmentList=[]
    current=[None,None]
    last=None
    for localization in sortedLocalizations:
        if current[0] is None:
            current[0] = localization.frame
            last = current[0]
        else:
            if localization.frame - 1 == last:
                last = localization.frame
            else:
                current[1] = last
                segmentList.append(current.copy())
                current[0] = localization.frame
                current[1] = None
                last = localization.frame
    if current[1] is None:
        current[1] = last
        segmentList.append(current)
    instance.segments = segmentList

class FrameAssociation(AssociationType):
    frame = PositiveIntegerField()
    extracted = ForeignKey(EntityMediaImage,
                           on_delete=SET_NULL,
                           null=True,
                           blank=True)

    def states(media_id):
        frameAssociations=FrameAssociation.objects.filter(media__in=media_id)
        return EntityState.objects.filter(association__in=frameAssociations)

class EntityState(EntityBase):
    """
    A State is an event that occurs, potentially independent, from that of
    a media element. It is associated with 0 (1 to be useful) or more media
    elements. If a frame is supplied it was collected at that time point.
    """
    association = ForeignKey(AssociationType, on_delete=CASCADE)
    version = ForeignKey(Version, on_delete=CASCADE, null=True, blank=True)
    modified = BooleanField(null=True, blank=True)
    """ Indicates whether an annotation is original or modified.
        null: Original upload, no modifications.
        false: Original upload, but was modified or deleted.
        true: Modified since upload or created via web interface.
    """

    def selectOnMedia(media_id):
        return AssociationType.states(media_id)

@receiver(post_save, sender=EntityState)
def state_save(sender, instance, created, **kwargs):
    TatorSearch().create_document(instance)

@receiver(pre_delete, sender=EntityState)
def state_delete(sender, instance, **kwargs):
    TatorSearch().delete_document(instance)

# Tree data type
class TreeLeaf(EntityBase):
    parent=ForeignKey('self', on_delete=SET_NULL, blank=True, null=True)
    path=PathField(unique=True)
    name = CharField(max_length=255)

    class Meta:
        verbose_name_plural = "TreeLeaves"

    def __str__(self):
        return str(self.path)

    def depth(self):
        return TreeLeaf.objects.annotate(depth=Depth('path')).get(pk=self.pk).depth

    def subcategories(self, minLevel=1):
        return TreeLeaf.objects.select_related('parent').filter(
            path__descendants=self.path,
            path__depth__gte=self.depth()+minLevel
        )

    def computePath(self):
        """ Returns the string representing the path element """
        pathStr=self.name.replace(" ","_").replace("-","_").replace("(","_").replace(")","_")
        if self.parent:
            pathStr=self.parent.computePath()+"."+pathStr
        elif self.project:
            projName=self.project.name.replace(" ","_").replace("-","_").replace("(","_").replace(")","_")
            pathStr=projName+"."+pathStr
        return pathStr

@receiver(post_save, sender=TreeLeaf)
def treeleaf_save(sender, instance, **kwargs):
    for ancestor in instance.computePath().split('.'):
        TatorCache().invalidate_treeleaf_list_cache(ancestor)
    TatorSearch().create_document(instance)

@receiver(pre_delete, sender=TreeLeaf)
def treeleaf_delete(sender, instance, **kwargs):
    for ancestor in instance.computePath().split('.'):
        TatorCache().invalidate_treeleaf_list_cache(ancestor)
    TatorSearch().delete_document(instance)

# Attribute types
# These table structures are used to describe the structure of
# an Entity's JSON-B attribute field

class AttributeTypeBase(PolymorphicModel):
    """ Generic entity in a JSON-B field.  """
    name = CharField(max_length=64)
    """ Name refers to the key in the JSON structure """
    description = CharField(max_length=256, blank=True)
    """ Human readable description of the column """
    applies_to = ForeignKey(EntityTypeBase, on_delete=CASCADE)
    """ Pointer to the owner of this type description. Either a media,
        state or sequence 'owns' this type and combines it into a set
        with other AttributeTypes to describe an AttributeSet """
    project = ForeignKey(Project, on_delete=CASCADE)
    order = IntegerField(default=0)
    """ Controls order (lower numbers first, negative is hide) """
    def __str__(self):
        return self.name

@receiver(post_save, sender=AttributeTypeBase)
def base_type_save(sender, instance, **kwargs):
    TatorSearch().create_mapping(instance)

class AttributeTypeBool(AttributeTypeBase):
    attr_name = "Boolean"
    dtype = "bool"
    default = BooleanField(null=True, blank=True)

@receiver(post_save, sender=AttributeTypeBool)
def bool_type_save(sender, instance, **kwargs):
    TatorSearch().create_mapping(instance)

class AttributeTypeInt(AttributeTypeBase):
    attr_name = "Integer"
    dtype = "int"
    default = IntegerField(null=True, blank=True)
    lower_bound = IntegerField(null=True, blank=True)
    upper_bound = IntegerField(null=True, blank=True)

@receiver(post_save, sender=AttributeTypeInt)
def int_type_save(sender, instance, **kwargs):
    TatorSearch().create_mapping(instance)

class AttributeTypeFloat(AttributeTypeBase):
    attr_name = "Float"
    dtype = "float"
    default = FloatField(null=True, blank=True)
    lower_bound = FloatField(null=True, blank=True)
    upper_bound = FloatField(null=True, blank=True)

@receiver(post_save, sender=AttributeTypeFloat)
def float_type_save(sender, instance, **kwargs):
    TatorSearch().create_mapping(instance)

class AttributeTypeEnum(AttributeTypeBase):
    attr_name = "Enum"
    dtype = "enum"
    choices = ArrayField(CharField(max_length=64))
    labels = ArrayField(CharField(max_length=64), null=True, blank=True)
    default = CharField(max_length=64, null=True, blank=True)

@receiver(post_save, sender=AttributeTypeEnum)
def enum_type_save(sender, instance, **kwargs):
    TatorSearch().create_mapping(instance)

class AttributeTypeString(AttributeTypeBase):
    attr_name = "String"
    dtype = "str"
    default = CharField(max_length=256, null=True, blank=True)
    autocomplete = JSONField(null=True, blank=True)

@receiver(post_save, sender=AttributeTypeString)
def string_type_save(sender, instance, **kwargs):
    TatorSearch().create_mapping(instance)

class AttributeTypeDatetime(AttributeTypeBase):
    attr_name = "Datetime"
    dtype = "datetime"
    use_current = BooleanField()
    default_timezone = CharField(max_length=3, null=True, blank=True)

@receiver(post_save, sender=AttributeTypeDatetime)
def datetime_type_save(sender, instance, **kwargs):
    TatorSearch().create_mapping(instance)

class AttributeTypeGeoposition(AttributeTypeBase):
    attr_name = "Geoposition"
    dtype = "geopos"
    default = PointField(null=True, blank=True)

@receiver(post_save, sender=AttributeTypeGeoposition)
def geopos_type_save(sender, instance, **kwargs):
    TatorSearch().create_mapping(instance)

def ProjectBasedFileLocation(instance, filename):
    return os.path.join(f"{instance.project.id}", filename)

class JobCluster(Model):
    name = CharField(max_length=128)
    owner = ForeignKey(User, null=True, blank=True, on_delete=SET_NULL)
    host = CharField(max_length=1024)
    port = PositiveIntegerField()
    token = CharField(max_length=1024)
    cert = TextField(max_length=2048)

    def __str__(self):
        return self.name

# Algorithm models

class Algorithm(Model):
    name = CharField(max_length=128)
    project = ForeignKey(Project, on_delete=CASCADE)
    user = ForeignKey(User, on_delete=PROTECT)
    description = CharField(max_length=1024, null=True, blank=True)
    manifest = FileField(upload_to=ProjectBasedFileLocation, null=True, blank=True)
    cluster = ForeignKey(JobCluster, null=True, blank=True, on_delete=SET_NULL)
    files_per_job = PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1),]
    )
    max_concurrent = PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1),]
    )

    def __str__(self):
        return self.name

def type_to_obj(typeObj):
    """Returns a data object for a given type object"""
    _dict = {
        EntityTypeLocalizationBox : EntityLocalizationBox,
        EntityTypeLocalizationLine : EntityLocalizationLine,
        EntityTypeLocalizationDot : EntityLocalizationDot,
        EntityTypeState : EntityState,
        EntityTypeMediaVideo : EntityMediaVideo,
        EntityTypeMediaImage : EntityMediaImage,
        EntityTypeTreeLeaf : TreeLeaf,
        }

    if typeObj in _dict:
        return _dict[typeObj]
    else:
        return None

class AnalysisBase(PolymorphicModel):
    project = ForeignKey(Project, on_delete=CASCADE)
    name = CharField(max_length=64)

class AnalysisCount(AnalysisBase):
    data_type = ForeignKey(EntityTypeBase, on_delete=CASCADE)
    data_query = CharField(max_length=1024, default='*')

class AnalysisPercentage(AnalysisBase):
    data_type = ForeignKey(EntityTypeBase, on_delete=CASCADE)
    numerator_filter = JSONField(null=True, blank=True)
    denominator_filter = JSONField(null=True, blank=True)

class AnalysisHistogram(AnalysisBase):
    data_type = ForeignKey(EntityTypeBase, on_delete=CASCADE)
    data_filter = JSONField(null=True, blank=True)
    attribute = ForeignKey(AttributeTypeBase, on_delete=CASCADE)
    plot_type = EnumField(HistogramPlotType)

class Analysis2D(AnalysisBase):
    data_type = ForeignKey(EntityTypeBase, on_delete=CASCADE)
    data_filter = JSONField(null=True, blank=True)
    attribute_x = ForeignKey(AttributeTypeBase, on_delete=CASCADE, related_name='attribute_x')
    attribute_y = ForeignKey(AttributeTypeBase, on_delete=CASCADE, related_name='attribute_y')
    plot_type = EnumField(TwoDPlotType)

class TemporaryFile(Model):
    """ Represents a temporary file in the system, can be used for algorithm results or temporary outputs """
    name = CharField(max_length=128)
    """ Human readable name for display purposes """
    project = ForeignKey(Project, on_delete=CASCADE)
    """ Project the temporary file resides in """
    user = ForeignKey(User, on_delete=PROTECT)
    """ User who created the temporary file """
    path = FilePathField(path=settings.MEDIA_ROOT, null=True, blank=True)
    """ Path to file on storage """
    lookup = SlugField(max_length=32)
    """ unique lookup (md5sum of something useful) """
    created_datetime = DateTimeField()
    """ Time that the file was created """
    eol_datetime = DateTimeField()
    """ Time the file expires (reaches EoL) """

    def expire(self):
        """ Set a given temporary file as expired """
        past = datetime.datetime.utcnow() - datetime.timedelta(hours=1)
        past = pytz.timezone("UTC").localize(past)
        self.eol_datetime = past
        self.save()

    def from_local(path, name, project, user, lookup, hours):
        """ Given a local file create a temporary file storage object
        :returns A saved TemporaryFile:
        """
        extension = os.path.splitext(name)[-1]
        destination_fp=os.path.join(settings.MEDIA_ROOT, f"{project.id}", f"{uuid.uuid1()}{extension}")
        os.makedirs(os.path.dirname(destination_fp), exist_ok=True)
        shutil.copyfile(path, destination_fp)

        now = datetime.datetime.utcnow()
        eol =  now + datetime.timedelta(hours=hours)

        temp_file = TemporaryFile(name=name,
                                  project=project,
                                  user=user,
                                  path=destination_fp,
                                  lookup=lookup,
                                  created_datetime=now,
                                  eol_datetime = eol)
        temp_file.save()
        return temp_file

@receiver(pre_delete, sender=TemporaryFile)
def temporary_file_delete(sender, instance, **kwargs):
    if os.path.exists(instance.path):
        os.remove(instance.path)
