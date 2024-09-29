import io
import base64
import os
import json
import time

from PIL import Image
import numpy as np

import omni
import omni.isaac.sensor as sensor
from omni.isaac.core.articulations import Articulation
from pxr import Gf, UsdGeom
from pxr.Usd import Prim as Prim

from foxglove_schemas_protobuf.CompressedImage_pb2 import CompressedImage
from foxglove_schemas_protobuf.FrameTransform_pb2 import FrameTransform
from foxglove_schemas_protobuf.FrameTransforms_pb2 import FrameTransforms
from foxglove_schemas_protobuf.Vector3_pb2 import Vector3
from foxglove_schemas_protobuf.Quaternion_pb2 import Quaternion

from .foxglove_wrapper import FoxgloveWrapper


class IsaacSensor():

    def __init__(self, sensor_type : str, sensor_path : str, cam_width : int = 128, cam_height : int = 128):
        self.type = sensor_type # ["camera", "imu", "articulation", "tf_tree"]
        self.path = sensor_path

        self.enabled = False

        if self.type == "camera":
            self.compressed = True
            self._sensor = sensor.Camera(self.path, resolution=(cam_width, cam_height))
            self._sensor.initialize()

        elif self.type == "imu":
            self._sensor = sensor._sensor.acquire_imu_sensor_interface()
        
        elif self.type == "articulation":
            self._sensor = Articulation(self.path)
            self._sensor.initialize()
        
        elif self.type == "tf_tree":
            self._sensor = omni.usd.get_context().get_stage()
        
        else:
            print("[Error] Invalid sensor type")
    

    def enable(self):
        self.enabled = True
    
    def disable(self):
        self.enabled = False


    def update_cam_resolution(self, width : int, height : int):
        """Changes the camera's resolution"""
        if self.type == "camera":

            self._sensor = sensor.Camera(self.path, resolution=(width, height))

            self._sensor.initialize()
        
        else:
            print("[Error] Not a camera")
    

    def collect(self):
        """Collect the current data from the sensor"""

        if self.type == "camera":
            return self.cam_collect()

        if self.type == "imu":
            return self.imu_collect()

        if self.type == "articulation":
            return self.articulation_collect()
        
        if self.type == "tf_tree":
            return self.tf_tree_collect()
    

    def cam_collect(self):
        """Get the current camera frame"""
        try:
            # Compressed Image (Protobuf)
            if self.compressed:
                image = self._sensor.get_rgb()
                frame = Image.fromarray(image)
                buffered = io.BytesIO()
                frame.save(buffered, format="jpeg")

                compressed_image = CompressedImage()
                compressed_image.format = "jpeg"
                compressed_image.data = buffered.getvalue()
                compressed_image.frame_id = self.path

                payload = compressed_image.SerializeToString()

            # Raw Image (Not used at the moment)
            else:
                image = self._sensor.get_rgb()
                frame = Image.fromarray(image)

                curr_dir = os.path.dirname(os.path.abspath(__file__))
                frame.save(curr_dir + "/test.png")

                width, height = frame.size
                encoding = "rgb8"
                step = width * 3

                raw_image_data = np.array(image).tobytes()
                frame_base64 = base64.b64encode(raw_image_data).decode('utf-8')
                data_frame = {"frame_id": self.path,
                              "width": width,
                              "height": height,
                              "encoding": encoding,
                              "step": step,
                              "data": frame_base64}

                payload = json.dumps(data_frame).encode("utf8")

        except Exception as e:
            print(e)
            return

        return payload
    

    def imu_collect(self):
        """Get the current IMU reading"""
        imu_out = None

        try:
            reading = self._sensor.get_sensor_reading(self.path)

            if reading.is_valid:
                imu_out = {"ang_vel_x": reading.ang_vel_x,
                           "ang_vel_y": reading.ang_vel_y,
                           "ang_vel_z": reading.ang_vel_z,
                           "lin_acc_x": reading.lin_acc_x,
                           "lin_acc_y": reading.lin_acc_y,
                           "lin_acc_z": reading.lin_acc_z,
                           "orientation": [reading.orientation.x,
                                           reading.orientation.y,
                                           reading.orientation.z,
                                           reading.orientation.w],
                           "time": reading.time}
        except:
            pass

        return json.dumps(imu_out).encode("utf8")
    

    def articulation_collect(self):
        """Get the current joint states (names, positions, velocities, efforts)"""
        joint_names = self._sensor.dof_names

        joint_states = {"joint_names": joint_names,
                        "joint_positions": self._sensor.get_joint_positions().tolist(),
                        "joint_velocities": self._sensor.get_joint_velocities().tolist(),
                        "joint_efforts": self._sensor.get_measured_joint_efforts().tolist()}
        
        return json.dumps(joint_states).encode("utf8")
    
    
    def tf_tree_collect(self):
        """Get the current transform tree"""
        self.transform_list = []

        root = self._sensor.GetPrimAtPath(self.path)
        self.fetch_transforms(root) # Populate self.transform_list

        transform_entries = []

        for matrix, parent_frame_id, child_frame_id in self.transform_list:
            transform_entries.append(
                self.create_transform_entry(matrix, parent_frame_id, child_frame_id)
            )

        tf = FrameTransforms()
        for transform_entry in transform_entries:
            tf.transforms.add().CopyFrom(transform_entry)
        payload = tf.SerializeToString()

        return payload
    
    def fetch_transforms(self, prim, parent_prim = None):
        prim_id = prim.GetName() # str(prim.GetPath())

        transform = UsdGeom.Xformable(prim)
        local_transform = transform.GetLocalTransformation()

        if parent_prim:
            self.transform_list.append((local_transform, parent_prim, prim_id))
        
        for child in prim.GetChildren():
            child_type = child.GetTypeName()
            if self.typeIsValid(child_type) and child.GetName() != "Render":
                self.fetch_transforms(child, prim_id)
    
    def typeIsValid(self, prim_type: str):
        return prim_type not in ["OmniGraph", "Scope", "Material"] \
                and "Joint" not in prim_type \
                and "Sensor" not in prim_type \
                and "Render" not in prim_type \

    def matrix_to_translation_rotation(self, matrix):
        translation = matrix.ExtractTranslation() # Extract translation
        rotation = Gf.Quatf(matrix.ExtractRotationQuat()) # Extract rotation as quaternion
        return translation, rotation
    
    def create_transform_entry(self, matrix, parent_frame_id, child_frame_id):
        translation, rotation = self.matrix_to_translation_rotation(matrix)

        translation_vect = Vector3()
        translation_vect.x = translation[0]
        translation_vect.y = translation[1]
        translation_vect.z = translation[2]

        rotation_quat = Quaternion()
        rotation_quat.x = rotation.GetImaginary()[0]
        rotation_quat.y = rotation.GetImaginary()[1]
        rotation_quat.z = rotation.GetImaginary()[2]
        rotation_quat.w = rotation.GetReal()

        transform_entry = FrameTransform()
        transform_entry.parent_frame_id = parent_frame_id
        transform_entry.child_frame_id = child_frame_id
        transform_entry.translation.CopyFrom(translation_vect)
        transform_entry.rotation.CopyFrom(rotation_quat)
        
        return transform_entry



class DataCollector():

    def __init__(self):
        """
        self.sensors = {"path1" : IsaacSensor(type1, path1),
                        "path2" : IsaacSensor(type2, path2),
                        "path3" : IsaacSensor(type3, path3)}
        """
        self.tf_root = "/"
        self.cam_width = 128
        self.cam_height = 128

        self.sensors = dict()
        self.sensors_sorted = {"camera" : set(),
                            "imu" : set(),
                            "articulation" : set(),
                            "tf_tree" : set()}
        
        self.fox_wrap = FoxgloveWrapper(self)
        

    def init_sensors(self):
        
        stage = omni.usd.get_context().get_stage()

        # Transform Tree
        root_path = str(stage.GetPseudoRoot().GetPath())
        self.sensors[root_path] = IsaacSensor("tf_tree", root_path)
        self.sensors_sorted["tf_tree"] = {root_path}

        self.update_sensors()


    def update_sensors(self):

        status = None
        stage = omni.usd.get_context().get_stage()

        stored_stage_objects = set(self.sensors.keys())
        actual_stage_objects = set(self.tf_root)

        # Add new prims
        for prim in stage.Traverse():
            prim_path = str(prim.GetPath())
            actual_stage_objects.add(prim_path)
            if prim_path not in stored_stage_objects:
                sensor_type = self.add_sensor(prim, cam_width=self.cam_width, cam_height=self.cam_height)
                if sensor_type:
                    status = f"\"{sensor_type}\" object added to stage"

        # Removed obsolete prims
        for prim_path in stored_stage_objects.difference(actual_stage_objects):
            sensor_type = self.remove_sensor(prim_path)
            if sensor_type:
                status = f"\"{sensor_type}\" object removed from stage"
            
        return status


    def add_sensor(self, prim : Prim, cam_width = 128, cam_height = 128, tf = False):
        prim_path = str(prim.GetPath())
        
        # TF Tree
        if tf:
            prim_type = "tf_tree"

        # Camera
        elif prim.IsA(UsdGeom.Camera):
            prim_type = "camera"

        # Imu
        elif prim.GetTypeName() == "IsaacImuSensor":
            prim_type = "imu"
        
        # Articulation
        elif "PhysicsArticulationRootAPI" in prim.GetAppliedSchemas():
            prim_type = "articulation"
        
        # Invalid
        else:
            prim_type = "invalid"
        
        if prim_type != "invalid":

            self.sensors[prim_path] = IsaacSensor(prim_type, prim_path, cam_width=cam_width, cam_height=cam_height)
            self.sensors_sorted[prim_type].add(prim_path)

            self.fox_wrap.add_channel(self.sensors[prim_path])

            return prim_type
        
    
    def remove_sensor(self, sensor_path : str):
        if sensor_path in self.sensors:

            sensor = self.sensors.pop(sensor_path)
            self.sensors_sorted[sensor.type].remove(sensor_path)

            self.fox_wrap.remove_channel(sensor_path)

            return sensor.type
    

    def set_cam_resolution(self, width : int, height : int):
        """Updates the resolution of existing and future cameras"""
        self.cam_width = width
        self.cam_height = height
        
        for path in self.sensors_sorted["camera"]:
            self.sensors[path].update_cam_resolution(width, height)


    def update_tf(self, new_tf_root):

        # Remove old
        if self.tf_root in self.sensors:
            self.remove_sensor(self.tf_root)
        
        # Add new
        self.tf_root = new_tf_root
        self.add_sensor(omni.usd.get_context().get_stage().GetPrimAtPath(self.tf_root), tf=True)
    

    def collect_data(self):
        data = dict()
        
        for sensor in self.sensors.values():
            if sensor.enabled:
                data[sensor.path] = sensor.collect()
        
        self.fox_wrap.send_message(data)
    

    def cleanup(self):
        self.fox_wrap.close()
        self.sensors = dict()
        self.sensors_sorted = {"camera" : set(),
                            "imu" : set(),
                            "articulation" : set(),
                            "tf_tree" : set()}