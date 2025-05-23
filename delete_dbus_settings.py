#!/usr/bin/env python3

import dbus
import sys

# --- Configuration ---
BUS_NAME = 'com.victronenergy.settings'

# The D-Bus object path where the RemoveSettings method is available.
# This is typically '/Settings' for the Victron settings service.
REMOVE_SETTINGS_OBJECT_PATH = '/Settings'

# The D-Bus interface that contains the RemoveSettings method.
REMOVE_SETTINGS_INTERFACE = 'com.victronenergy.Settings' # <-- REMAINS CAPITALIZED

# List of *relative* paths to delete. These paths are relative to REMOVE_SETTINGS_OBJECT_PATH.
# Example: If REMOVE_SETTINGS_OBJECT_PATH is '/Settings', and you want to delete
# /Settings/RemoteGPIO/GPIO1/Type, you would list 'RemoteGPIO/GPIO1/Type'.
#
# IMPORTANT: Replace with the actual relative paths you want to delete.
SETTINGS_TO_DELETE = [
]
# Example: ["RemoteGPIO/GPIO1/Type", "RemoteGPIO/GPIO2/Polarity"]


# --- D-Bus Helper Functions ---

def _get_dbus_object_proxy(bus_name, object_path):
    """Helper to get a D-Bus object proxy for a given object path."""
    try:
        bus = dbus.SystemBus() # Victron Venus OS uses the System Bus for these services
        # Use the lowercase bus_name here
        obj = bus.get_object(bus_name, object_path)
        return obj
    except dbus.exceptions.DBusException as e:
        print(f"Error connecting to D-Bus or getting object proxy for {object_path}: {e}", file=sys.stderr)
        return None

def introspect_dbus_service(bus_name, object_path):
    """
    Introspects a D-Bus object and prints its XML description,
    which lists available interfaces, methods, signals, and properties.
    """
    try:
        bus = dbus.SystemBus()
        # Use the lowercase bus_name here for introspection
        obj = bus.get_object(bus_name, object_path, introspect=False)

        introspect_iface = dbus.Interface(obj, 'org.freedesktop.DBus.Introspectable')
        xml_data = introspect_iface.Introspect()

        print(f"\n--- D-Bus Introspection for {bus_name} at {object_path} ---")
        print(xml_data)
        print("-----------------------------------------------------------------\n")

    except dbus.exceptions.DBusException as e:
        print(f"Error during D-Bus introspection for {bus_name} at {object_path}: {e}", file=sys.stderr)
    except Exception as e:
        print(f"An unexpected error occurred during introspection: {e}", file=sys.stderr)


def remove_victron_settings(settings_to_remove):
    """
    Calls the RemoveSettings method on the com.victronenergy.Settings service
    using the specified interface and object path.

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
        # Get the D-Bus object proxy for the specified path
        # Use the lowercase BUS_NAME here
        settings_obj = _get_dbus_object_proxy(BUS_NAME, REMOVE_SETTINGS_OBJECT_PATH)
        if not settings_obj:
            sys.exit(1) # Error already printed

        # Get the D-Bus interface that contains the RemoveSettings method.
        # This uses the capitalized REMOVE_SETTINGS_INTERFACE.
        settings_interface = dbus.Interface(settings_obj, REMOVE_SETTINGS_INTERFACE)

        # Call the RemoveSettings method with the list of paths.
        # dbus.Array is crucial for D-Bus list types, with signature='s' for strings.
        settings_interface.RemoveSettings(dbus.Array(settings_to_remove, signature='s'))

        print("\nSuccessfully sent request to remove settings.")
        print("Please note: D-Bus changes are usually persistent after this call.")
        print("A reboot of Venus OS might be required for some changes to take full effect in dependent services.")

    except dbus.exceptions.DBusException as e:
        print(f"Error calling RemoveSettings: {e}", file=sys.stderr)
        print("This typically means:")
        print("  1. The D-Bus service is not running.")
        print("  2. You do not have sufficient permissions (try running as root).")
        print(f"  3. The method 'RemoveSettings' is not found on interface '{REMOVE_SETTINGS_INTERFACE}' at object path '{REMOVE_SETTINGS_OBJECT_PATH}' on your system (double-check introspection output).")
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)

# --- Main Script Execution ---

if __name__ == "__main__":
    # Always perform introspection first to aid in debugging
    print("--- Starting D-Bus Introspection ---")
    # Use the lowercase BUS_NAME for introspection
    introspect_dbus_service(BUS_NAME, REMOVE_SETTINGS_OBJECT_PATH)
    print("--- D-Bus Introspection Complete ---")

    if not SETTINGS_TO_DELETE:
        print("Error: The SETTINGS_TO_DELETE list is empty. Please populate it with the relative D-Bus paths you wish to remove.")
        print("Example: SETTINGS_TO_DELETE = ['RemoteGPIO/GPIO1/Type', 'RemoteGPIO/GPIO2/Polarity']")
        sys.exit(1)

    remove_victron_settings(SETTINGS_TO_DELETE)
