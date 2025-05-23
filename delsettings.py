#!/usr/bin/env python3

import dbus
import sys

# --- Configuration ---
BUS_NAME = 'com.victronenergy.settings'
# The D-Bus object path where the RemoveSettings method is available.
# For removing settings under /Settings/RemoteGPIO, you typically call RemoveSettings
# on the /Settings object path and provide relative paths.
# Based on Victron documentation/examples, /Settings is the common path for this.
REMOVE_SETTINGS_OBJECT_PATH = '/Settings'

# List of *relative* paths to delete. These paths are relative to REMOVE_SETTINGS_OBJECT_PATH.
# So, if REMOVE_SETTINGS_OBJECT_PATH is '/Settings', and you want to delete
# /Settings/RemoteGPIO/GPIO1/Type, you would list 'RemoteGPIO/GPIO1/Type'.
#
# IMPORTANT: Replace with the actual relative paths you want to delete.
# Examples:
# SETTINGS_TO_DELETE = [
#     "RemoteGPIO/GPIO1/Type",
#     "RemoteGPIO/GPIO1/Polarity",
#     "RemoteGPIO/GPIO2/Type",
#     "RemoteGPIO/GPIO2/Function"
# ]
SETTINGS_TO_DELETE = [] # <-- Populate this list with the settings you want to remove!
                        # Example: ["RemoteGPIO/GPIO1/Type", "RemoteGPIO/GPIO2/Polarity"]

# --- D-Bus Helper Functions ---

def _get_dbus_interface(bus_name, object_path, interface_name=None):
    """Helper to get a D-Bus interface for a given object path."""
    try:
        bus = dbus.SystemBus() # Victron Venus OS uses the System Bus for these services
        obj = bus.get_object(bus_name, object_path)
        if interface_name:
            return dbus.Interface(obj, interface_name)
        else:
            # If no interface name, return the generic object for introspection/method calls
            return obj
    except dbus.exceptions.DBusException as e:
        print(f"Error connecting to D-Bus or getting interface for {object_path}: {e}", file=sys.stderr)
        return None

def remove_victron_settings(settings_to_remove):
    """
    Calls the RemoveSettings method on the com.victronenergy.settings service.

    Args:
        settings_to_remove (list): A list of relative D-Bus paths (strings) to delete.
    """
    if not settings_to_remove:
        print("No settings paths provided to remove. Exiting.")
        return

    print(f"Connecting to D-Bus service: {BUS_NAME} at object path: {REMOVE_SETTINGS_OBJECT_PATH}")
    print(f"Attempting to remove the following settings:")
    for path in settings_to_remove:
        print(f"  - {path}")

    confirmation = input("\nAre you sure you want to permanently remove these D-Bus settings? (yes/no): ").lower()
    if confirmation != "yes":
        print("Operation cancelled.")
        sys.exit(0)

    try:
        # Get the D-Bus object for the specified path
        settings_obj = _get_dbus_interface(BUS_NAME, REMOVE_SETTINGS_OBJECT_PATH)
        if not settings_obj:
            sys.exit(1) # Error already printed

        # Get the D-Bus interface that contains the RemoveSettings method
        # This is typically on the main service object (no specific interface needed for direct method call)
        # However, for clarity and robustness, we can specify the BusItem interface if it has it,
        # or just rely on direct method call on the proxy object if the method is root-level.
        # Based on Victron examples, it's often a direct method on the top-level object path.
        settings_interface = dbus.Interface(settings_obj, BUS_NAME) # Or 'org.freedesktop.DBus.Properties' or similar if method is not root

        # Call the RemoveSettings method with the list of paths
        # dbus.Array is important for D-Bus list types.
        settings_interface.RemoveSettings(dbus.Array(settings_to_remove, signature='s'))

        print("\nSuccessfully sent request to remove settings.")
        print("Please note: D-Bus changes are usually persistent after this call.")
        print("A reboot of Venus OS might be required for some changes to take full effect in dependent services.")

    except dbus.exceptions.DBusException as e:
        print(f"Error calling RemoveSettings: {e}", file=sys.stderr)
        print("Please ensure the D-Bus service is running and you have appropriate permissions (e.g., run as root).")
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)

# --- Main Script Execution ---

if __name__ == "__main__":
    if not SETTINGS_TO_DELETE:
        print("Error: The SETTINGS_TO_DELETE list is empty. Please populate it with the relative D-Bus paths you wish to remove.")
        print("Example: SETTINGS_TO_DELETE = ['RemoteGPIO/GPIO1/Type', 'RemoteGPIO/GPIO2/Polarity']")
        sys.exit(1)

    remove_victron_settings(SETTINGS_TO_DELETE)
