import asyncio
import json
import time
import os

from foxglove_websocket.server import FoxgloveServer, FoxgloveServerListener
from foxglove_websocket.types import ChannelId

from foxglove_websocket.types import (
    ChannelId,
)

from .schemas import get_schema_for_sensor


# Terminal text formatting
class Colors:
    RESET = "\033[0m"
    MAGENTA = "\033[35m"
    MAGENTA_BOLD = MAGENTA + "\033[1m"


def get_topic_for_sensor(sensor):

    if sensor.type == "tf_tree":
        return "/tf"

    suffix = ""
    if sensor.type == "articulation":
        suffix = "/joint_states"
    # Add suffixes for future supported format here
    
    return sensor.path + suffix


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
            print(Colors.MAGENTA_BOLD + f"[Foxglove Info] Foxglove server closed" + Colors.RESET)


    async def _run_server(self, port : int, sensors : dict):
        try:
            async with FoxgloveServer("0.0.0.0", port, "isaac sim server") as self.server:
                self.server.set_listener(Listener(self.data_collector, self.channel2path))

                await self.init_channels(sensors)

                print(Colors.MAGENTA_BOLD + f"[Foxglove Info] Foxglove server started at ws://0.0.0.0:{port}" + Colors.RESET)

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

        schema_name, schema_file = get_schema_for_sensor(sensor)
        topic_name = get_topic_for_sensor(sensor)

        with open(schema_path + schema_file, 'r') as schema_file:
            schema = json.load(schema_file)
        
        self.path2channel[sensor.path] = await self.server.add_channel(
            {
                "topic": topic_name,
                "encoding": "json",
                "schemaName": schema_name,
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
            if self.server and payload:
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
        path = self.channel2path[channel_id]
        topic = get_topic_for_sensor(self.data_collector.sensors[path])
        self.data_collector.sensors[path].enable()
        print(Colors.MAGENTA_BOLD + f"[Foxglove Info] First client subscribed to {topic}" + Colors.RESET)

    async def on_unsubscribe(self, server: FoxgloveServer, channel_id: ChannelId):
        path = self.channel2path[channel_id]
        if path in self.data_collector.sensors:
            topic = get_topic_for_sensor(self.data_collector.sensors[path])
            self.data_collector.sensors[path].disable()
            print(Colors.MAGENTA_BOLD + f"[Foxglove Info] Last client unsubscribed from {topic}" + Colors.RESET)