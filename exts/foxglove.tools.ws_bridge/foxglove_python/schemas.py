
type2json = {"camera_raw" :{
                "file": "RawImage.json",
                "name" : "foxglove.RawImage"
            },
             "camera": {
                "file": "CompressedImage.json",
                "name": "foxglove.CompressedImage"
            },
             "imu" : {
                "file": "Imu.json",
                "name": "IMU"
            },
             "articulation" : {
                "file": "JointStates.json",
                "name": "JointStates"
            },
             "tf_tree" : {
                "file": "FrameTransforms.json",
                "name": "foxglove.FrameTransforms"
            }}


def get_schema_for_sensor(sensor):

    name = type2json[sensor.type]["name"]
    file = type2json[sensor.type]["file"]

    return name, file