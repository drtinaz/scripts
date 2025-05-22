#!/usr/bin/env python

import dbus
import sys
import time
from gi.repository import GLib

# Add the path to our own packages for import (adjust if your velib_python path is different)
# This is crucial for systems where velib_python is not in the default Python path.
sys.path.insert(1, "/data/SetupHelper/velib_python")
from ve_utils import wrap_dbus_value


dbusSystemPath = "com.victronenergy.system"

class TestMonitor:
    def __init__(self):
        self.theBus = dbus.SystemBus()
        self.transferSwitchStateObj = None
        self.transferSwitchActive = False
        self.currentLimitObj = None
        self.veBusService = ""
        self.tsInputSearchDelay = 99  # allow search to occur immediately
        self.custom_transfer_switch_name_found = False # New flag to track if custom name is found

    def updateTransferSwitchState(self):
        inputValid = False
        # If transfer switch is currently active, try to get its state
        if self.transferSwitchActive:
            try:
                state = self.transferSwitchStateObj.GetValue()
                if state == 12 or state == 3:  # 12 and 3 are on generator values
                    inputValid = True
                    print("Digital Input State: On Generator (12 or 3)")
                elif state == 13 or state == 2:  # 13 and 2 are on grid values
                    inputValid = True
                    print("Digital Input State: On Grid (13 or 2)")
                else:
                    print(f"Digital Input State: Unknown ({state})")
            except dbus.exceptions.DBusException as e:
                print(f"DEBUG: DBus Error getting transfer switch state from known object: {e}")
                pass

        # If input is not valid or we need to search for a new one
        if not inputValid and self.transferSwitchActive:
            print("Digital input for transfer switch no longer valid. Searching for a new one...")
            self.transferSwitchActive = False
            self.custom_transfer_switch_name_found = False

        # Search for a new digital input service every 10 seconds to avoid unnecessary processing
        if not inputValid and self.tsInputSearchDelay >= 10:
            print("DEBUG: Initiating search for digital input service...")
            newInputService = ""
            for service in self.theBus.list_names():
                if service.startswith("com.victronenergy.digitalinput"):
                    print(f"DEBUG: Found digital input service: {service}")
                    try:
                        obj_path = '/CustomName' # Path to the custom name
                        temp_custom_name_obj = self.theBus.get_object(service, obj_path)
                        custom_name = temp_custom_name_obj.GetValue()
                        print(f"DEBUG: Checking CustomName for service {service}: '{custom_name}'")

                        if "transfer switch" in custom_name.lower():
                            print(f"DEBUG: Found 'transfer switch' in CustomName for service {service}.")
                            # Now verify it has a '/State' property for actual use
                            try:
                                # This just checks if the /State object exists and can be read
                                self.theBus.get_object(service, '/State').GetValue()
                                newInputService = service
                                break
                            except dbus.exceptions.DBusException as e:
                                print(f"DEBUG: Service {service} has 'transfer switch' in custom name but no valid '/State' property: {e}")
                                pass

                    except dbus.exceptions.DBusException as e:
                        print(f"DEBUG: Service {service} does not have a '/CustomName' property or an error occurred: {e}")
                        pass
                else:
                    print(f"DEBUG: Skipping service (not digitalinput): {service}")

            # Found new service - set up to use its values
            if newInputService != "":
                print(f"Discovered transfer switch digital input service at {newInputService} based on custom name.")
                self.transferSwitchStateObj = self.theBus.get_object(newInputService, '/State')
                self.transferSwitchActive = True
                self.custom_transfer_switch_name_found = True
            elif self.transferSwitchActive: # This case should not be reached if newInputService is "" and transferSwitchActive was True
                print("Transfer switch digital input service NOT found (no match by custom name).")
                self.transferSwitchActive = False
                self.custom_transfer_switch_name_found = False


        if self.transferSwitchActive:
            self.tsInputSearchDelay = 0
        else:
            # If search delay timer is active, increment it now
            if self.tsInputSearchDelay < 10:
                self.tsInputSearchDelay += 1
            else:
                self.tsInputSearchDelay = 0
            if not self.custom_transfer_switch_name_found:
                print(f"DEBUG: Still searching for digital input... next search in {10 - self.tsInputSearchDelay} seconds.")


    def getAcInputCurrent(self):
        vebusService = ""
        try:
            obj = self.theBus.get_object(dbusSystemPath, '/VebusService')
            vebusService = obj.GetText()
        except dbus.exceptions.DBusException as e:
            if self.veBusService:
                print(f"DEBUG: Multi/Quattro disappeared - /VebusService invalid: {e}")
            self.veBusService = ""
            self.currentLimitObj = None
            return

        if vebusService == "---":
            if self.veBusService != "":
                print("DEBUG: Multi/Quattro disappeared (service string is '---')")
            self.vebusService = ""
            self.currentLimitObj = None
        elif self.vebusService == "" or vebusService != self.vebusService:
            self.vebusService = vebusService
            try:
                self.currentLimitObj = self.theBus.get_object(vebusService, "/Ac/ActiveIn/CurrentLimit")
                print(f"Discovered VE.Bus service at {vebusService}")
            except dbus.exceptions.DBusException as e:
                print(f"DEBUG: DBus Error setting up current limit object: {e} - cannot get AC input current.")
                self.currentLimitObj = None

        if self.currentLimitObj:
            try:
                current_limit = self.currentLimitObj.GetValue()
                print(f"Active AC Input Current Limit: {current_limit} A")
            except dbus.exceptions.DBusException as e:
                print(f"DEBUG: DBus Error getting AC input current limit: {e}")
        else:
            print("AC Input Current Limit object not available.")


    def background(self):
        print("\n--- Checking Status ---")
        self.updateTransferSwitchState()
        self.getAcInputCurrent()
        return True # Keep the GLib.timeout_add running

def main():
    from dbus.mainloop.glib import DBusGMainLoop

    DBusGMainLoop(set_as_default=True)

    print("Starting ExtTransferSwitch test script...")

    monitor = TestMonitor()

    # Run the background function every 1 second
    GLib.timeout_add(1000, monitor.background)

    mainloop = GLib.MainLoop()
    try:
        mainloop.run()
    except KeyboardInterrupt:
        print("\nExiting...")

if __name__ == "__main__":
    main()
