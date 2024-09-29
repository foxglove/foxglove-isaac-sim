# Code Overview

## extension.py
A class containing the standard boilerplate necessary to have the extension show up on the Toolbar.
In extension.py, useful standard callback functions are created and are completed in ui_builder.py.

## ui_builder.py
This file contains the extension's main code.  Here, the UI is created and each element is hooked up to custom callback functions talking to the Foxglove Wrapper running the Server.

## data_collection.py
This file contains the custom IsaacSensor class and the DataCollector class handling all the sensor data queries. This is where sensors are automatically sorted according to their types.

## foxglove_wrapper.py
A class running the Foxglove Server in parallel with the simulation. It handles channel definitions, additions, removals, and sending messages.