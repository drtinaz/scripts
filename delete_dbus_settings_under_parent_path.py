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

# The parent path for settings to delete
PARENT_PATH = '/Settings/RemoteGPIO'

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

def _get_all_children_paths(bus_name, parent_path):
    """
    Recursively gets all D-Bus object paths under a given parent path
    that expose the com.victronenergy.BusItem interface.
    This uses introspection, which might be slow for very large trees.
    """
    all_paths = []
    try:
        bus = dbus.SystemBus()
        obj = bus.get_object(bus_name, parent_path)
        introspect_iface = dbus.Interface(obj, dbus.INTROSPECTABLE_INTERFACE)
        xml = introspect_iface.Introspect()

        import xml.etree.ElementTree as ET
        root = ET.fromstring(xml)

        for node in root.findall('node'):
            node_name = node.get('name')
            if node_name:
                child_path = f"{parent_path}/{node_name}"
                all_paths.extend(_get_all_children_paths(bus_name, child_path))

        # Check if the current object_path itself has the desired interface
        for interface_node in root.findall('interface'):
            if interface_node.get('name') == 'com.victronenergy.BusItem':
                # Check for a 'GetValue' method as a proxy for being a settable item
                # This ensures we only add actual "items" and not just parent nodes.
                if any(method.get('name') == 'GetValue' for method in interface_node.findall('method')):
                    all_paths.append(parent_path)
                break # Only need to find the interface once per object

    except dbus.exceptions.DBusException as e:
        # This is common when a path exists in the hierarchy but isn't an actual
        # D-Bus object with interfaces. Just skip it.
        # print(f"Debug: Could not introspect {parent_path} (might not be an object): {e}", file=sys.stderr)
        pass
    except ET.ParseError as e:
        print(f"Error parsing XML for {parent_path}: {e}", file=sys.stderr)
    return all_paths

# --- Main Script Execution ---

if __name__ == "__main__":
    print(f"Connecting to D-Bus service: {BUS_NAME}")
    print(f"Targeting settings under path: {PARENT_PATH}")

    # Discover all settable paths under PARENT_PATH
    all_paths = _get_all_children_paths(BUS_NAME, PARENT_PATH)
    # Remove the PARENT_PATH itself from the list, as we only want the children
    if PARENT_PATH in all_paths:
        all_paths.remove(PARENT_PATH)

    if not all_paths:
        print(f"No settable D-Bus paths found under '{PARENT_PATH}'. Exiting.")
        sys.exit(0)

    # Convert to relative paths
    SETTINGS_TO_DELETE = [path.replace(PARENT_PATH + '/', '', 1) for path in all_paths]

    print("\nSettings to be removed:")
    for path in SETTINGS_TO_DELETE:
        print(f"  - {path}")

    remove_victron_settings(SETTINGS_TO_DELETE)
