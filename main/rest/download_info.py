import os
import logging
from uuid import uuid1

import boto3
from rest_framework.exceptions import PermissionDenied

from ..models import Project
from ..schema import DownloadInfoSchema
from ..s3 import TatorS3

from ._base_views import BaseListView
from ._permissions import ProjectTransferPermission

logger = logging.getLogger(__name__)

class DownloadInfoAPI(BaseListView):
    """ Retrieve info needed to download a file.
    """
    schema = DownloadInfoSchema()
    permission_classes = [ProjectTransferPermission]
    http_method_names = ['post']

    def _post(self, params):

        # Parse parameters.
        keys = params['keys']
        expiration = params['expiration']
        project = params['project']
        s3 = TatorS3()
        response_data = []
        for key in keys:
            if key.startswith('/'):
                # Not an s3 key, just return the key as url.
                url = key
            else:
                # Make sure the key corresponds to the correct project.
                project_from_key = int(key.split('/')[1])
                if project != project_from_key:
                    raise PermissionDenied
                # Generate presigned url.
                url = s3.get_download_url(key, expiration)
            response_data.append({'key': key, 'url': url})
        return response_data

