#!/usr/bin/env python3

from gi.repository import GLib
import logging
import sys
import os
import random
import configparser
import subprocess
import time

# Set up logging for both the launcher and the child processes
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# A more reliable way to find velib_python
try:
    sys.path.insert(1, "/opt/victronenergy/dbus-systemcalc-py/ext/velib_python")
    from vedbus import VeDbusService
except ImportError:
    logger.critical("Cannot find vedbus library. Please ensure it's in the correct path.")
    sys.exit(1)

def generate_random_serial(length=16):
    """
    Generates a random serial number of a given length.
    """
    return ''.join([str(random.randint(0, 9)) for _ in range(length)])

class DbusMyTestSwitch(VeDbusService):

    def __init__(self, service_name, device_config, output_configs, serial_number):
        super().__init__(service_name)

        # General device settings
        self.add_path('/Mgmt/ProcessName', 'dbus-victron-virtual')
        self.add_path('/Mgmt/ProcessVersion', '0.1.16')
        self.add_path('/Mgmt/Connection', 'Virtual')
        
        # Get values from the device-specific config section
        self.add_path('/DeviceInstance', device_config.getint('DeviceInstance'))
        self.add_path('/ProductId', 49257)
        self.add_path('/ProductName', 'Virtual switch')
        self.add_path('/CustomName', device_config.get('CustomName'))
        
        # We are now using the randomly generated serial number.
        self.add_path('/Serial', serial_number)
        
        self.add_path('/State', 256)
        
        self.add_path('/FirmwareVersion', 0)
        self.add_path('/HardwareVersion', 0)
        self.add_path('/Connected', 1)

        # Loop through the outputs and add their D-Bus paths
        for output_data in output_configs:
            self.add_output(output_data)
        
        # Register the service on the D-Bus
        self.register()
        logger.info(f"Service '{service_name}' for device '{device_config.get('CustomName')}' registered on D-Bus.")

    def add_output(self, output_data):
        """
        Adds a single switchable output and its settings to the D-Bus service.
        """
        output_prefix = f'/SwitchableOutput/output_{output_data["index"]}'

        self.add_path(f'{output_prefix}/Name', output_data['name'])
        self.add_path(f'{output_prefix}/Status', 0)

        # Add the State path, which will be writable.
        self.add_path(f'{output_prefix}/State', 0, writeable=True, onchangecallback=self.handle_change)

        settings_prefix = f'{output_prefix}/Settings'
        self.add_path(f'{settings_prefix}/CustomName', output_data['custom_name'], writeable=True)
        self.add_path(f'{settings_prefix}/Group', output_data['group'], writeable=True)
        self.add_path(f'{settings_prefix}/Type', 1, writeable=True)
        self.add_path(f'{settings_prefix}/ValidTypes', 7)

    def handle_change(self, path, value, _context):
        """
        Callback function to handle changes to D-Bus paths.
        """
        logger.info(f"Received a change request for {path} to value {value}")
        
        if "/State" in path:
            if value not in [0, 1]:
                logger.warning(f"Invalid state value received: {value}")
                return False
            
            logger.info(f"Switch state for {path} changed to {value}")
            self[path] = value
            return True
        else:
            logger.warning(f"Unhandled change request for path: {path}")
            return False

def run_device_service(device_index):
    """
    Main function for a single D-Bus service process.
    """
    # Setup D-Bus main loop
    from dbus.mainloop.glib import DBusGMainLoop
    DBusGMainLoop(set_as_default=True)
    
    config_file_path = os.path.join(os.path.dirname(__file__), 'config.ini')
    
    config = configparser.ConfigParser()
    if not os.path.exists(config_file_path):
        logger.critical(f"Configuration file not found: {config_file_path}")
        sys.exit(1)
    
    try:
        config.read(config_file_path)
    except configparser.Error as e:
        logger.critical(f"Error parsing configuration file: {e}")
        sys.exit(1)

    device_section = f'Device_{device_index}'
    if not config.has_section(device_section):
        logger.critical(f"Configuration section '{device_section}' not found. Cannot start.")
        sys.exit(1)
        
    device_config = config[device_section]
    
    try:
        num_switches = device_config.getint('NumberOfSwitches')
    except (configparser.NoOptionError, ValueError):
        logger.warning(f"No 'NumberOfSwitches' found for {device_section}. Defaulting to 1 switch.")
        num_switches = 1

    output_configs = []
    for j in range(1, num_switches + 1):
        output_section = f'Output_{device_index}_{j}'
        
        if not config.has_section(output_section):
            custom_name = ''
            group = ''
        else:
            output_settings = config[output_section]
            custom_name = output_settings.get('CustomName', '')
            group = output_settings.get('Group', '')
        
        output_data = {
            'index': j,
            'name': f'Switch {j}',
            'custom_name': custom_name,
            'group': group,
        }
        output_configs.append(output_data)

    # Generate a random serial number
    random_serial = generate_random_serial()
    
    # Use the random serial number for the D-Bus service name
    service_name = f'com.victronenergy.switch.virtual_{random_serial}'
    DbusMyTestSwitch(service_name, device_config, output_configs, random_serial)
    
    logger.info('Connected to D-Bus, and switching over to GLib.MainLoop() (= event based)')
    
    mainloop = GLib.MainLoop()
    mainloop.run()

def main():
    """
    The main launcher function that runs as the parent process.
    """
    config_file_path = os.path.join(os.path.dirname(__file__), 'config.ini')
    
    config = configparser.ConfigParser()
    if not os.path.exists(config_file_path):
        logger.critical(f"Configuration file not found: {config_file_path}")
        sys.exit(1)
    
    try:
        config.read(config_file_path)
        logger.info(f"Configuration file '{config_file_path}' loaded successfully.")
    except configparser.Error as e:
        logger.critical(f"Error parsing configuration file: {e}")
        sys.exit(1)

    try:
        num_devices = config.getint('Global', 'NumberOfDevices')
    except (configparser.NoSectionError, configparser.NoOptionError):
        logger.warning("No 'NumberOfDevices' found in [Global] section. Defaulting to 1 device.")
        num_devices = 1

    # Get the path to the current script
    script_path = os.path.abspath(sys.argv[0])
    
    processes = []
    
    logger.info(f"Starting {num_devices} virtual switch device processes...")

    for i in range(1, num_devices + 1):
        device_section = f'Device_{i}'
        
        if not config.has_section(device_section):
            logger.warning(f"Configuration section '{device_section}' not found. Skipping device {i}.")
            continue
            
        # We pass the device index to the child process via command-line argument.
        cmd = [sys.executable, script_path, str(i)]
        
        try:
            process = subprocess.Popen(cmd, env=os.environ, close_fds=True)
            processes.append(process)
            logger.info(f"Started process for virtual device {i} (PID: {process.pid})")
        except Exception as e:
            logger.error(f"Failed to start process for device {i}: {e}")
            
    try:
        # Keep the launcher process running.
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Terminating all child processes.")
        for p in processes:
            p.terminate()
        for p in processes:
            p.wait()

if __name__ == "__main__":
    # Check if a command-line argument was provided
    if len(sys.argv) > 1:
        # If so, this is a child process. Run the service.
        run_device_service(sys.argv[1])
    else:
        # Otherwise, this is the main launcher process.
        main()
