#!/usr/bin/env python3
import subprocess
import sys
import os

def read_settings_from_config(filename):
    """
    Reads a list of D-Bus settings paths from a text configuration file.

    Args:
        filename (str): The path to the configuration file.

    Returns:
        list: A list of strings, where each string is a D-Bus setting path.
              Returns an empty list if the file is not found or is empty.
    """
    settings_paths = []
    try:
        with open(filename, 'r') as f:
            for line in f:
                # Strip leading/trailing whitespace and ignore empty lines or comments
                path = line.strip()
                if path and not path.startswith('#'):
                    settings_paths.append(path)
        return settings_paths
    except FileNotFoundError:
        print(f"Error: Configuration file '{filename}' not found.", file=sys.stderr)
        return []
    except Exception as e:
        print(f"An unexpected error occurred while reading the config file: {e}", file=sys.stderr)
        return []

def remove_dbus_settings(settings_paths):
    """
    Removes a list of D-Bus settings using the dbus command line tool.

    Args:
        settings_paths (list): A list of strings, where each string is the
                               path to a D-Bus setting to be removed.
    """
    if not settings_paths:
        print("No settings paths found to remove. Exiting.")
        return

    # Check if input is a list of strings
    if not isinstance(settings_paths, list) or not all(isinstance(p, str) for p in settings_paths):
        print("Error: Input must be a list of strings.", file=sys.stderr)
        return

    # Correctly format the list of paths for the D-Bus command.
    # The required format is "%["/path1", "/path2", ...]"
    dbus_array_contents = '", "'.join(settings_paths)
    dbus_arg = f'%["{dbus_array_contents}"]'

    command = [
        "dbus",
        "-y",
        "com.victronenergy.settings",
        "/Settings",
        "RemoveSettings",
        dbus_arg
    ]

    print(f"Attempting to remove the following settings: {settings_paths}")
    try:
        # Use subprocess.run to execute the command
        result = subprocess.run(
            command,
            check=True,  # Raise an exception if the command fails
            capture_output=True,
            text=True
        )
        print("Command executed successfully.")
        print("STDOUT:")
        print(result.stdout)
        if result.stderr:
            print("STDERR:")
            print(result.stderr)

    except FileNotFoundError:
        print(f"Error: The 'dbus' command was not found. Please ensure it is installed and in your PATH.", file=sys.stderr)
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {e}", file=sys.stderr)
        print(f"Return code: {e.returncode}", file=sys.stderr)
        print(f"STDOUT: {e.stdout}", file=sys.stderr)
        print(f"STDERR: {e.stderr}", file=sys.stderr)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)

if __name__ == "__main__":
    # Define the name of the configuration file
    config_file = "settings_to_delete.conf"
    
    # Read the settings paths from the config file
    paths_to_remove = read_settings_from_config(config_file)

    # Call the function with the list of paths from the config file
    remove_dbus_settings(paths_to_remove)
