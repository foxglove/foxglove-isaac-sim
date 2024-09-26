# Copyright (c) 2022-2023, NVIDIA CORPORATION. All rights reserved.
#
# NVIDIA CORPORATION and its licensors retain all intellectual property
# and proprietary rights in and to this software, related documentation
# and any modifications thereto. Any use, reproduction, disclosure or
# distribution of this software and related documentation without an express
# license agreement from NVIDIA CORPORATION is strictly prohibited.
#

import os
from typing import List
import time

import omni.ui as ui
from omni.isaac.ui.element_wrappers import (
    Button,
    CheckBox,
    Frame,
    CollapsableFrame,
    ColorPicker,
    DropDown,
    FloatField,
    IntField,
    StateButton,
    StringField,
    TextBlock,
    XYPlot,
)
from omni.isaac.ui.ui_utils import get_style

import omni
from pxr import Usd, UsdGeom, UsdPhysics

from .data_collection import DataCollector
# from .foxglove_wrapper import FoxgloveWrapper

class UIBuilder:
    def __init__(self):
        # Frames are sub-windows that can contain multiple UI elements
        self.frames = []

        # UI elements created using a UIElementWrapper from omni.isaac.ui.element_wrappers
        self.wrapped_ui_elements = []

        self._status_report_field = TextBlock(
                    "Last UI Event",
                    num_lines=3,
                    tooltip="Prints the latest change to this UI",
                    include_copy_button=True,
                )

        # Foxglove inits
        self.data_collect = DataCollector()
        self.publishing = False
        self.last_saved_port = 8765
        self.server_port = 8765
        self.cam_width = 128
        self.cam_height = 128


    ###################################################################################
    #           The Functions Below Are Called Automatically By extension.py
    ###################################################################################

    def on_menu_callback(self):
        """Callback for when the UI is opened from the toolbar.
        This is called directly after build_ui().
        """
        pass

    def on_timeline_event(self, event):
        """Callback for Timeline events (Play, Pause, Stop)

        Args:
            event (omni.timeline.TimelineEventType): Event Type
        """
        pass

    def on_physics_step(self, step):
        """Callback for Physics Step.
        Physics steps only occur when the timeline is playing

        Args:
            step (float): Size of physics step
        """
        if self.publishing:
            self.data_collect.collect_data()

    def on_stage_event(self, event):
        """Callback for Stage Events

        Args:
            event (omni.usd.StageEventType): Event Type
        """
        if event.type == 23: # When an object is added or removed from stage

            # Update sensors
            status = self.data_collect.update_sensors()
            if status:
                self._status_report_field.set_text(status)

            # Update UI
            self._update_camera_frame()
            self._update_imu_frame()
            self._update_articulation_frame()
            self.tf_root_dropdown.repopulate()

    def cleanup(self):
        """
        Called when the stage is closed or the extension is hot reloaded.
        Perform any necessary cleanup such as removing active callback functions
        Buttons imported from omni.isaac.ui.element_wrappers implement a cleanup function that should be called
        """
        # None of the UI elements in this template actually have any internal state that needs to be cleaned up.
        # But it is best practice to call cleanup() on all wrapped UI elements to simplify development.
        for ui_elem in self.wrapped_ui_elements:
            ui_elem.cleanup()
        
        # Foxglove objects
        self.data_collect.fox_wrap.close()

    def build_ui(self):
        """
        Build a custom UI tool to run your extension.
        This function will be called any time the UI window is closed and reopened.
        """
        if not self.data_collect.sensors:
            self.data_collect.init_sensors()
        
        self.data_collect.update_sensors()

        # Create a UI frame for text description
        self._create_description_frame()

        # Create a UI frame for Refresh and Update buttons
        self._create_spacer(10)
        self._create_publish_button()
        self._create_spacer(10)

        # Create a UI frame for the list of Cameras
        self._create_camera_frame()

        # Create a UI frame for the list of IMUs
        self._create_imu_frame()

        # Create a UI frame for the list of Articulations
        self._create_articulation_frame()

        # Create a UI frame for the root frame selection for TF Tree
        self._create_settings_frame()

        # Create a UI frame that prints the latest UI event.
        self._create_spacer(20)
        self._create_status_report_frame()

        status = "UI window was opened"
        self._status_report_field.set_text(status)

        # Start server once everything is initialized
        self.data_collect.fox_wrap.start(self.server_port, self.data_collect.sensors)
        self.publishing = True


    def _create_description_frame(self):
        self._description_frame = Frame()
        with self._description_frame:
            with ui.VStack(style=get_style(), spacing=5, height=0):
                self.description = ui.Label(
                    "   Welcome to the Foxglove Extension for Isaac Sim!\n" +
                    "   To view in Foxglove, open a new connection from\n" +
                    "   your Foxglove dashboard to the following URL:\n" +
                    "   ws://localhost:<port> (default port is 8765).\n\n"
                    "   Below is the list of all the data automatically detected\n" + 
                    "   by the extension, organized by type. You can access\n" +
                    "   each of these data streams within Foxglove. Under \n" +
                    "   \"Settings\", you can specify the server port, the camera\n" +
                    "   resolution, and the frame that should serve as the\n" +
                    "   root for the transform tree."
                )

    def _create_publish_button(self):
        self._publish_button_frame = Frame()
        with self._publish_button_frame:
            with ui.VStack(style=get_style(), spacing=5, height=0):

                publish_button = StateButton(
                    "   Publishing Status",
                    "Publishing",
                    "Not Publishing",
                    tooltip="Click this button to toggle publishing to Foxglove using the current settings",
                    on_a_click_fn=self._on_publish_off_click_fn,
                    on_b_click_fn=self._on_publish_on_click_fn,
                    physics_callback_fn=None,  # See Loaded Scenario Template for example usage
                )
                self.wrapped_ui_elements.append(publish_button)


    def _create_camera_frame(self):
        self._camera_frame = CollapsableFrame("Cameras", collapsed=False)
        self._update_camera_frame()
    
    def _update_camera_frame(self):
        with self._camera_frame:
            with ui.VStack(style=get_style(), spacing=5, height=0):
                for cam in self.data_collect.sensors_sorted["camera"]:
                    ui.Label(cam)


    def _create_imu_frame(self):
        self._imu_frame = CollapsableFrame("IMUs", collapsed=False)
        self._update_imu_frame()
    
    def _update_imu_frame(self):
        with self._imu_frame:
            with ui.VStack(style=get_style(), spacing=5, height=0):
                for imu in self.data_collect.sensors_sorted["imu"]:
                    ui.Label(imu)


    def _create_articulation_frame(self):
        self._articulation_frame = CollapsableFrame("Articulations", collapsed=False)
        self._update_articulation_frame()
    
    def _update_articulation_frame(self):
        with self._articulation_frame:
            with ui.VStack(style=get_style(), spacing=5, height=0):
                for articulation in self.data_collect.sensors_sorted["articulation"]:
                    ui.Label(articulation)


    def _create_settings_frame(self):
        self._settings_frame = CollapsableFrame("Settings", collapsed=True)
        with self._settings_frame:
            with ui.VStack(style=get_style(), spacing=5, height=0):
                self._create_server_port_frame()
                self._create_camera_resolution_frame()
                self._create_tf_root_frame()


    def _create_server_port_frame(self):
        self._server_port_frame = CollapsableFrame("Server Port", collapsed=False)
        with self._server_port_frame:
            with ui.VStack(style=get_style(), spacing=5, height=0):
                server_port_intfield = IntField("Port",
                                                tooltip="Change the port for the Foxglove server)",
                                                default_value=self.server_port,
                                                lower_limit=0,
                                                upper_limit=9999,
                                                on_value_changed_fn=self._on_port_changed)
                self.wrapped_ui_elements.append(server_port_intfield)

                apply_button = Button("Set Server Port",
                                      "Apply",
                                      tooltip="Click on \"Apply\" to set new server port",
                                      on_click_fn=self._on_port_applied)
                self.wrapped_ui_elements.append(apply_button)


    def _create_camera_resolution_frame(self):
        self._camera_resolution_frame = CollapsableFrame("Camera Resolution", collapsed=False)
        with self._camera_resolution_frame:
            with ui.VStack(style=get_style(), spacing=5, height=0):
                camera_width_intfield = IntField("Width",
                                                 tooltip="Change the width of the camera\n(the larger the slower)",
                                                 default_value=self.cam_width,
                                                 lower_limit=0,
                                                 upper_limit=1280,
                                                 on_value_changed_fn=self._on_width_changed)
                self.wrapped_ui_elements.append(camera_width_intfield)

                camera_height_intfield = IntField("Height",
                                                tooltip="Change the height of the camera\n(the larger the slower)",
                                                default_value=self.cam_height,
                                                lower_limit=0,
                                                upper_limit=800,
                                                on_value_changed_fn=self._on_height_changed)
                self.wrapped_ui_elements.append(camera_height_intfield)

                apply_button = Button("Set Resolution",
                                     "Apply",
                                     tooltip="Click on \"Apply\" to set new camera resolution",
                                     on_click_fn=self._on_resolution_save)
                self.wrapped_ui_elements.append(apply_button)
    

    def _create_tf_root_frame(self):
        self._tf_root_frame = CollapsableFrame("Transform Tree Root", collapsed=False)
        with self._tf_root_frame:
            with ui.VStack(style=get_style(), spacing=5, height=0):
                
                def tf_root_dropdown_populate_fn():
                    root_options = ["/"]
                    stage = omni.usd.get_context().get_stage()
                    for prim in stage.Traverse():
                        if len(prim.GetChildren()) and prim.GetTypeName() not in ["OmniGraph", "RenderProduct", "Scope", "Material"]:
                            root_options.append(str(prim.GetPath()))
                            
                    return root_options

                self.tf_root_dropdown = DropDown(
                    "Root",
                    tooltip="Select the root for the Transform Tree to be published",
                    populate_fn=tf_root_dropdown_populate_fn,
                    on_selection_fn=self._on_tf_root_selection_fn,
                    keep_old_selections=True,
                )
                self.wrapped_ui_elements.append(self.tf_root_dropdown)

                self.tf_root_dropdown.repopulate()


    def _create_line(self):
        line_frame = Frame()
        with line_frame:
            with ui.VStack(style=get_style(), spacing=5, height=0):
                ui.Line()

    def _create_spacer(self, size : int):
        spacer_frame = Frame()
        with spacer_frame:
            with ui.VStack(style=get_style(), spacing=5, height=0):
                ui.Spacer(height=size)

    def _create_status_report_frame(self):
        self._status_report_frame = CollapsableFrame("Status Report", collapsed=True)
        with self._status_report_frame:
            with ui.VStack(style=get_style(), spacing=5, height=0):
                self._status_report_field = TextBlock(
                    "Last UI Event",
                    num_lines=3,
                    tooltip="Prints the latest change to this UI",
                    include_copy_button=True,
                )

    ######################################################################################
    # Functions Below This Point Are Callback Functions Attached to UI Element Wrappers
    ######################################################################################

    def _on_publish_on_click_fn(self):
        self.data_collect.fox_wrap.start(self.server_port, self.data_collect.sensors)
        self.publishing = True
        status = "Foxglove server started at:\nws://0.0.0.0:" + str(self.server_port)
        self._status_report_field.set_text(status)
    
    def _on_publish_off_click_fn(self):
        self.data_collect.fox_wrap.close()
        self.publishing = False
        status = "Foxglove server closed"
        self._status_report_field.set_text(status)

    def _on_port_changed(self, port : int):
        self.server_port = port

    def _on_port_applied(self):
        self.last_saved_port = self.server_port
        if self.publishing:
            self.data_collect.fox_wrap.close()
            self.data_collect.fox_wrap.start(self.server_port, self.data_collect.sensors)
        status = f"Server port was set to {self.server_port}"
        self._status_report_field.set_text(status)

    def _on_width_changed(self, width : int):
        self.cam_width = width

    def _on_height_changed(self, height : int):
        self.cam_height = height

    def _on_resolution_save(self):
        self.data_collect.set_cam_resolution(self.cam_width, self.cam_height)
        status = f"Camera resolution set to {self.cam_width}x{self.cam_height}"
        self._status_report_field.set_text(status)

    def _on_tf_root_selection_fn(self, item : str):
        self.data_collect.update_tf(item)
        status = f"Transform Tree root was set to {item}"
        self._status_report_field.set_text(status)