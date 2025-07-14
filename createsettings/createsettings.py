#!/usr/bin/env python3

# Import necessary libraries
import sys
import os
import dbus
from gi.repository import GLib

# Adjust the system path to find the velib_python library
sys.path.insert(1, os.path.join(os.path.dirname(__file__), '/opt/victronenergy/dbus-systemcalc-py/ext/velib_python'))
from settingsdevice import SettingsDevice

# Define your D-Bus settings
# The SettingsDevice class requires a dictionary where each key is a friendly name,
# and the value is a list containing the D-Bus path, initial value, and two reserved values.
settingsList = {
    'customSetting1': ['/Settings/MyCustomApp/MyFirstSetting', 100, 0, 0],
    'customSetting2': ['/Settings/MyCustomApp/AnotherSetting', 'some text', 0, 0],
    'customSetting3': ['/Settings/MyCustomApp/AFloatSetting', 5.5, 0, 0],
    'customSetting4': ['/Settings/MyCustomApp/SomeBoolean', 0, 0, 0] # 0 for False, 1 for True
}

def create_dbus_settings():
    """
    Creates and attaches to the D-Bus settings service.
    """
    # Set up the D-Bus main loop.
    # This is required for the SettingsDevice class to work correctly.
    from dbus.mainloop.glib import DBusGMainLoop
    DBusGMainLoop(set_as_default=True)

    # Get a handle to the D-Bus system bus
    bus = dbus.SystemBus()

    try:
        # Create an instance of SettingsDevice.
        # This will register the settings on the D-Bus under com.victronenergy.settings
        # if they do not already exist.
        my_dbus_settings = SettingsDevice(
            bus=bus,
            supportedSettings=settingsList,
            timeout=10,
            eventCallback=None
        )

        print("D-Bus settings created successfully:")
        for key, value in settingsList.items():
            path = value[0]
            current_value = my_dbus_settings[key]
            print(f"- Path: {path}, Initial Value: {value[1]}, Current Value: {current_value}")

    except Exception as e:
        print(f"An error occurred: {e}")

    # The script must remain running to keep the settings published.
    # Use GLib.MainLoop to keep the script alive.
    mainloop = GLib.MainLoop()
    mainloop.run()

if __name__ == '__main__':
    create_dbus_settings()
