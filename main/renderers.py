from rest_framework.renderers import BaseRenderer

import csv
import io
import ujson

from collections import OrderedDict
from pprint import pprint

class CsvRenderer(BaseRenderer):
    """ renders an object (list of objects) to a CSV file """
    media_type = 'text/plain'
    format = 'csv'

    def render(self, listObj, media_type=None, renderer_context=None):
        """ Flattens list of objects into a CSV """
        temp_file=io.StringIO()
        temp_list=[]
        return_value="No Records found."
        try:
            if listObj:
                field_names=listObj[0].keys()
                for entry in listObj:
                    row_object={}
                    for field in field_names:
                        if type(entry[field]) in [OrderedDict, dict]:
                            row_object.update(entry[field])
                        else:
                            row_object[field] = entry[field]
                    temp_list.append(row_object)
                field_names=temp_list[0].keys()
                writer=csv.DictWriter(temp_file,
                                      fieldnames=field_names,
                                      extrasaction='ignore')
                writer.writeheader()
                writer.writerows(temp_list)
                return_value=temp_file.getvalue()
        except Exception as e:
            return_value=str(e)
        finally:
            return return_value

class PprintRenderer(BaseRenderer):
    """ renders an object (list of objects) to a CSV file """
    media_type = 'application/json'
    format = 'pprint'

    def render(self, listObj, media_type=None, renderer_context=None):
        """ Returns a pretty printed representation of the list object """
        temp_file=io.StringIO()
        pprint(listObj, temp_file)
        return temp_file.getvalue()


class UJsonRenderer(BaseRenderer):
    """ Uses ujson instead of json to serialize an object """
    media_type = 'application/json'
    format = 'json'

    def render(self, obj, media_type=None, renderer_context=None):
        return ujson.dumps(obj, ensure_ascii=True, escape_forward_slashes=False)

class JpegRenderer(BaseRenderer):
    media_type = 'image/jpeg'
    charset = None
    format = 'jpg'

    def render(self, data, media_type=None, renderer_context=None):
        return data

class PngRenderer(BaseRenderer):
    media_type = 'image/png'
    charset = None
    format = 'png'

    def render(self, data, media_type=None, renderer_context=None):
        return data

class GifRenderer(BaseRenderer):
    media_type = 'image/gif'
    charset = None
    format = 'gif'

    def render(self, data, media_type=None, renderer_context=None):
        return data

class Mp4Renderer(BaseRenderer):
    media_type = 'video/mp4'
    charset = None
    format = 'mp4'

    def render(self, data, media_type=None, renderer_context=None):
        return data
