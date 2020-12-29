from typing import Dict, List
from textwrap import dedent

from rest_framework.schemas.openapi import AutoSchema

from ._errors import error_responses
from ._message import message_schema
from ._attribute_type import attribute_type_example
from ._entity_type_mixins import entity_type_filter_parameters_schema

boilerplate = dedent("""\
A attribute type is the metadata definition object for a user-defined attribute. It includes
name, type, and any other associated fields, depending on the type.
""")

class AttributeTypeListSchema(AutoSchema):
    def get_operation(self, path, method):
        operation = super().get_operation(path, method)

        if method == "POST":
            operation["operationId"] = "AddAttribute"
        elif method == "PATCH":
            operation["operationId"] = "RenameAttribute"

        operation["tags"] = ["Tator"]

        return operation

    def get_description(self, path, method):
        if method == "POST":
            short_desc = "Add attribute to Type."
        elif method == "PATCH":
            short_desc = "Rename and/or change the type of an existing attribute on Type."
        return f"{short_desc}\n\n{boilerplate}"

    def _get_path_parameters(self, path, method):
        return [{
            "name": "id",
            "in": "path",
            "required": True,
            "description": "A unique integer identifying a unique entity type.",
            "schema": {"type": "integer"},
        }]

    def _get_filter_parameters(self, path, method):
        return []

    def _get_request_body(self, path, method):
        body = {}
        if method == "POST":
            body = {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/AttributeAddition"},
                        "example": {
                            "entity_type": "LocalizationType",
                            "addition": attribute_type_example[1],
                        },
                    }
                },
            }
        elif method == "PATCH":
            body = {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/AttributeRename"},
                        "example": {
                            "entity_type": "LocalizationType",
                            "old_attribute_type_name": "My Old Attribute",
                            "new_attribute_type": attribute_type_example[3],
                        },
                    }
                },
            }
        return body

    def _get_responses(self, path, method):
        responses = error_responses()
        if method == "PATCH":
            responses["200"] = message_schema("update", "attribute")
        elif method == "POST":
            responses["201"] = message_schema("creation", "attribute")
        return responses
