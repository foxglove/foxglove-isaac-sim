import threading
import asyncio
import json
import time
import os
import logging

from typing import Any, Coroutine, Dict

from foxglove_websocket.server import FoxgloveServer, FoxgloveServerListener
from foxglove_websocket import run_cancellable
from foxglove_websocket.types import ChannelId, ChannelWithoutId

from foxglove_websocket.types import (
    ChannelId,
    ClientChannel,
    ClientChannelId,
    ServiceId,
)


# Maps sensor types to json schema files and names
type2json = {"camera_raw" : {"file": "RawImage.json", "name" : "foxglove.RawImage"},
             "camera": {"file": "CompressedImage.json", "name": "foxglove.CompressedImage"},
             "imu" : {"file": "Imu.json", "name": "IMU"},
             "articulation" : {"file": "JointStates.json", "name": "JointStates"},
             "tf_tree" : {"file": "FrameTransforms.json", "name": "foxglove.FrameTransforms"}}

# Maps sensor types to topic names
type2topic = {"camera" : "",
              "imu" : "",
              "articulation" : "/joint_states",
              "tf_tree" : "tf"}


class FoxgloveWrapper():

    def __init__(self, data_collector):
        self.data_collector = data_collector
        self.server = None

        self.path2channel = dict()  # Maps sensor paths to channel IDs
        self.channel2path = dict()  # Inverse map

    def start(self, port: int, sensors : dict):
        loop = asyncio.get_event_loop()
        self.server_task = loop.create_task(self._run_server(port, sensors))
    
    def close(self):
        if self.server:
            self.server_task.cancel()
            self.server = None


    async def _run_server(self, port : int, sensors : dict):
        try:
            async with FoxgloveServer("0.0.0.0", port, "isaac sim server") as self.server:
                self.server.set_listener(Listener(self.data_collector, self.channel2path))

                await self.init_channels(sensors)

                while True:
                    await asyncio.sleep(1)

        except asyncio.CancelledError:
            pass


    async def init_channels(self, sensors : dict):

        curr_dir = os.path.dirname(os.path.abspath(__file__))
        schema_path = os.path.join(curr_dir, 'json_schemas/')

        for sensor in sensors.values():
            await self._add_channel(sensor, schema_path)


    def add_channel(self, sensor):

        curr_dir = os.path.dirname(os.path.abspath(__file__))
        schema_path = os.path.join(curr_dir, 'json_schemas/')

        loop = asyncio.get_event_loop()
        if self.server:
            loop.create_task(self._add_channel(sensor, schema_path))


    async def _add_channel(self, sensor, schema_path : str):

        with open(schema_path + type2json[sensor.type]["file"], 'r') as schema_file:
            schema = json.load(schema_file)
        
        self.path2channel[sensor.path] = await self.server.add_channel(
            {
                "topic": "/tf" if sensor.type == "tf_tree" else sensor.path + type2topic[sensor.type],
                "encoding": "json",
                "schemaName": type2json[sensor.type]["name"],
                "schema": json.dumps(schema),
                "schemaEncoding": "jsonschema",
            }
        )

        self.channel2path[self.path2channel[sensor.path]] = sensor.path

    
    def remove_channel(self, sensor_path : str):
        loop = asyncio.get_event_loop()
        if self.server:
            loop.create_task(self._remove_channel(sensor_path))


    async def _remove_channel(self, sensor_path : str):
        await self.server.remove_channel(self.path2channel[sensor_path])
        chan_id = self.path2channel.pop(sensor_path)
        self.channel2path.pop(chan_id)


    def send_message(self, data : dict):
        loop = asyncio.get_event_loop()
        if self.server:
            loop.create_task(self._send_message(data))
            

    async def _send_message(self, data : dict):
        for path, payload in data.items():
            if payload:
                await self.server.send_message(
                    self.path2channel[path],
                    time.time_ns(),
                    json.dumps(payload).encode("utf8"),
                )

    

class Listener(FoxgloveServerListener):

    def __init__(self, data_collector, channel2path : dict):
        self.data_collector = data_collector
        self.channel2path = channel2path

    async def on_subscribe(self, server: FoxgloveServer, channel_id: ChannelId):
        self.data_collector.sensors[self.channel2path[channel_id]].enable()
        print("First client subscribed to", channel_id)

    async def on_unsubscribe(self, server: FoxgloveServer, channel_id: ChannelId):
        self.data_collector.sensors[self.channel2path[channel_id]].disable()
        print("Last client unsubscribed from", channel_id)