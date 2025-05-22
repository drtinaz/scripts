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

    def updateTransferSwitchState(self):
        inputValid = False
        # If transfer switch is currently active, try to get its state
        if self.transferSwitchActive:
            try:
                state = self.transferSwitchStateObj.GetValue()
                if state == 12:  # 12 is the on generator value
                    inputValid = True
                    print("Digital Input State: On Generator (12)")
                elif state == 13:  # 13 is the on grid value
                    inputValid = True
                    print("Digital Input State: On Grid (13)")
                else:
                    print(f"Digital Input State: Unknown ({state})")
            except dbus.exceptions.DBusException as e:
                print(f"DBus Error getting transfer switch state: {e}")
                pass

        # If input is not valid or we need to search for a new one
        if not inputValid and self.transferSwitchActive:
            print("Transfer switch digital input no longer valid. Searching for a new one...")
            self.transferSwitchActive = False

        # Search for a new digital input service every 10 seconds to avoid unnecessary processing
        if not inputValid and self.tsInputSearchDelay >= 10:
            newInputService = ""
            for service in self.theBus.list_names():
                # Found a digital input service, now check for valid state value
                if service.startswith("com.victronenergy.digitalinput"):
                    try:
                        temp_transferSwitchStateObj = self.theBus.get_object(service, '/State')
                        state = temp_transferSwitchStateObj.GetValue()
                        # Found it!
                        if state == 12 or state == 13:
                            newInputService = service
                            break
                    except dbus.exceptions.DBusException as e:
                        # Ignore errors - continue to check for other services
                        print(f"DBus Error checking digital input service {service}: {e}")
                        pass

            # Found new service - set up to use its values
            if newInputService != "":
                print(f"Discovered transfer switch digital input service at {newInputService}")
                self.transferSwitchStateObj = self.theBus.get_object(newInputService, '/State')
                self.transferSwitchActive = True
            elif self.transferSwitchActive:
                print("Transfer switch digital input service NOT found")
                self.transferSwitchActive = False

        if self.transferSwitchActive:
            self.tsInputSearchDelay = 0
        else:
            # If search delay timer is active, increment it now
            if self.tsInputSearchDelay < 10:
                self.tsInputSearchDelay += 1
            else:
                self.tsInputSearchDelay = 0

    def getAcInputCurrent(self):
        vebusService = ""
        try:
            obj = self.theBus.get_object(dbusSystemPath, '/VebusService')
            vebusService = obj.GetText()
        except dbus.exceptions.DBusException as e:
            if self.veBusService:
                print(f"Multi/Quattro disappeared - /VebusService invalid: {e}")
            self.veBusService = ""
            self.currentLimitObj = None
            return

        if vebusService == "---":
            if self.veBusService != "":
                print("Multi/Quattro disappeared")
            self.veBusService = ""
            self.currentLimitObj = None
        elif self.veBusService == "" or vebusService != self.veBusService:
            self.veBusService = vebusService
            try:
                self.currentLimitObj = self.theBus.get_object(vebusService, "/Ac/ActiveIn/CurrentLimit")
                print(f"Discovered VE.Bus service at {vebusService}")
            except dbus.exceptions.DBusException as e:
                print(f"DBus Error setting up current limit object: {e} - cannot get AC input current.")
                self.currentLimitObj = None

        if self.currentLimitObj:
            try:
                current_limit = self.currentLimitObj.GetValue()
                print(f"Active AC Input Current Limit: {current_limit} A")
            except dbus.exceptions.DBusException as e:
                print(f"DBus Error getting AC input current limit: {e}")
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
