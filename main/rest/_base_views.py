""" TODO: add documentation for this """
import traceback
import logging

from rest_framework.views import APIView
from rest_framework.request import Request as DrfRequest
from rest_framework.response import Response as DrfDrfResponse
from rest_framework.exceptions import PermissionDenied
from rest_framework import status
from django.core.exceptions import ObjectDoesNotExist
from django.http import response

from ..schema import parse

logger = logging.getLogger(__name__)

def process_exception(exc: Exception) -> DrfResponse:
    """process_exception handles exceptions raised in http methods in the Detail/List views.

    :param Exception exc:
    """
    logger.info("Handling Exception!")
    logger.info(type(exc))
    if isinstance(exc, response.Http404):
        resp = DrfResponse({'message' : str(exc)},
                        status=status.HTTP_404_NOT_FOUND)
    elif isinstance(exc, ObjectDoesNotExist):
        logger.error(f"Not found in GET request: {str(exc)}")
        resp = DrfResponse({'message' : str(exc)},
                        status=status.HTTP_404_NOT_FOUND)
    elif isinstance(exc, PermissionDenied):
        logger.error(f"Permission denied error: {str(exc)}")
        resp = DrfResponse({'message': str(exc)},
                        status=status.HTTP_403_FORBIDDEN)
    else:
        logger.error(f"Exception in request: {traceback.format_exc()}")
        resp = DrfResponse({'message' : str(exc),
                         'details': traceback.format_exc()},
                        status=status.HTTP_400_BAD_REQUEST)
    return resp

class GetMixin:
    """GetMixin provides the get http method for a View class.
    """

    #pylint: disable=redefined-builtin,unused-argument
    def get(self, request: DrfRequest, format=None, **kwargs) -> DrfResponse:
        """get is the http get method for a View. It calls the _get method
           provided by the subclass.
        """
        resp = DrfResponse({})
        params = parse(request)
        response_data = self._get(params)
        resp = DrfResponse(response_data, status=status.HTTP_200_OK)
        return resp

class PostMixin:
    """PostMixin provides the post http method for a View class.
    """
    #pylint: disable=redefined-builtin,unused-argument
    def post(self, request: DrfRequest, format=None, **kwargs) -> DrfResponse:
        """post is the http post method for a View. It calls the _post method
           provided by the subclass.
        """
        resp = DrfResponse({})
        params = parse(request)
        response_data = self._post(params)
        resp = DrfResponse(response_data, status=status.HTTP_201_CREATED)
        return resp

class PatchMixin:
    """PatchMixin provides the patch http method for a View class.
    """
    #pylint: disable=redefined-builtin,unused-argument
    def patch(self, request: DrfRequest, format=None, **kwargs) -> DrfResponse:
        """patch is the http patch method for a View. It calls the _patch
           method provided by the subclass.
        """
        params = parse(request)
        response_data = self._patch(params)
        resp = DrfResponse(response_data, status=status.HTTP_200_OK)
        return resp

class DeleteMixin:
    """DeleteMixin provides the delete http method for a View class.
    """
    #pylint: disable=redefined-builtin,unused-argument
    def delete(self, request: DrfRequest, format=None, **kwargs) -> DrfResponse:
        """delete is the http delete method for a View. It calls the _delete
           method provided by the subclass.
        """
        params = parse(request)
        response_data = self._delete(params)
        resp = DrfResponse(response_data, status=status.HTTP_200_OK)
        return resp

class BaseListView(APIView, GetMixin, PostMixin, PatchMixin, DeleteMixin):
    """ Base class for list views.
    """
    http_method_names = ['get', 'post', 'patch', 'delete']

    def handle_exception(self, exc: Exception) -> DrfResponse:
        return process_exception(exc)

class BaseDetailView(APIView, GetMixin, PatchMixin, DeleteMixin):
    """ Base class for detail views.
    """
    http_method_names = ['get', 'patch', 'delete']

    def handle_exception(self, exc: Exception) -> DrfResponse:
        return process_exception(exc)
