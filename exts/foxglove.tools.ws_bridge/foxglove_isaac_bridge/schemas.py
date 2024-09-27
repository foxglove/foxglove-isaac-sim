import os
import json
from base64 import b64encode
from typing import Set, Type

from foxglove_schemas_protobuf.CompressedImage_pb2 import CompressedImage
from foxglove_schemas_protobuf.FrameTransforms_pb2 import FrameTransforms

import google.protobuf.message
from google.protobuf.descriptor_pb2 import FileDescriptorSet
from google.protobuf.descriptor import FileDescriptor


type2schema = {
                "camera_raw" :{
                    "file": "RawImage.json",
                    "name" : "foxglove.RawImage",
                    "encoding" : "json",
                },
                "camera": {
                    "file": CompressedImage,
                    "name": CompressedImage.DESCRIPTOR.full_name,
                    "encoding" : "protobuf",
                },
                "imu" : {
                    "file": "Imu.json",
                    "name": "IMU",
                    "encoding" : "json",
                },
                "articulation" : {
                    "file": "JointStates.json",
                    "name": "JointStates",
                    "encoding" : "json",
                },
                "tf_tree" : {
                    "file": FrameTransforms,
                    "name": FrameTransforms.DESCRIPTOR.full_name,
                    "encoding" : "protobuf",
                }
              }

encoding2schema = {"json" : "jsonschema",
                   "protobuf" : "protobuf"}


def build_file_descriptor_set(
    message_class: Type[google.protobuf.message.Message],
) -> FileDescriptorSet:
    """
    Build a FileDescriptorSet representing the message class and its dependencies.
    """
    file_descriptor_set = FileDescriptorSet()
    seen_dependencies: Set[str] = set()

    def append_file_descriptor(file_descriptor: FileDescriptor):
        for dep in file_descriptor.dependencies:
            if dep.name not in seen_dependencies:
                seen_dependencies.add(dep.name)
                append_file_descriptor(dep)
        file_descriptor.CopyToProto(file_descriptor_set.file.add())  # type: ignore

    append_file_descriptor(message_class.DESCRIPTOR.file)
    return file_descriptor_set


def load_schema_for_type(sensor_type):

    encoding = type2schema[sensor_type]["encoding"]
    file = type2schema[sensor_type]["file"]

    if encoding == "json":
        curr_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(curr_dir, 'json_schemas/')
        with open(json_path + file, 'r') as schema_file:
            json_schema = json.load(schema_file)
        return json.dumps(json_schema)

    elif encoding == "protobuf":
        return b64encode(build_file_descriptor_set(file).SerializeToString()).decode("ascii")


def get_schema_for_sensor(sensor):
    """Returns name, schema, encoding, schemaEncoding"""

    name = type2schema[sensor.type]["name"]
    schema = load_schema_for_type(sensor.type)
    encoding = type2schema[sensor.type]["encoding"]
    schemaEncoding = encoding2schema[encoding]

    return name, schema, encoding, schemaEncoding