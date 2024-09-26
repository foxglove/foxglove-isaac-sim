# Changelog

## [0.1.0] - 2024-09-04

Initial version of the Foxglove Extension: hard-coded for the Quadruped Isaac Example

## [1.0.0] - 2024-09-20

### Added

- Graphical User Interface to allow for the selection of data sources (limited to 1 source per type)
- Buttons to start/stop Foxglove server

## [1.1.0] - 2024-09-24

### Added

- Unlimited channels
- Automatic and dynamic update of sensors
- Sensors only queried when corresponding topic is subscribed to
- New menu item to open Foxglove Dashboard in browser

### Removed

- Manual source selection for Cameras, IMUs and Articulations

## [1.2.0] - 2024-09-25

### Added

- "View in Foxglove" button to directly open a WebSocket client in browser
- Server starts automatically
- Settings collapsable menu in the extension tab
- Can set server port manually
- Can choose camera resolution
- Can select root frame for TF tree

### Removed

- Button to start/stop server