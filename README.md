copy and paste the code below into ssh terminal of the venus os device to download and install one of the following services:
1. auto_switch https://github.com/drtinaz/auto_switch

   (automatically enables/disables a relay/switch based on the ac input source. Handy for mobile vehicles with ac water heater installed.)
2. auto_current https://github.com/drtinaz/auto_current

   (automatically calculates the derated maximum ac current limit allowed for a generator based on outdoor temp, generator temp, and altitude.)
3. autogen https://github.com/drtinaz/autogen

   (combines the functions of both the auto current service and the transfer switch service into one.)
4. gps_socat https://github.com/drtinaz/gps_socat

   (listens to an external gps socat data stream and publishes that data to dbus on com.victronenergy.gps.xxx)
5. external_devices https://github.com/drtinaz/external_devices

   (creates dbus services for externally connected devices such as relay modules, switches, digital inputs, temperature sensors, tank sensors, pv chargers, and batteries. uses mqtt topic subscription. includes auto discovery mechanism for dingtian relay modules and shelly switches.)

6. transfer_switch https://github.com/drtinaz/transfer_switch

   (automatically changes the ac input source between shore/grid and generator based on the state of an external transfer switch.saves and restores current limit settings for each)

7. mp2_emulator https://github.com/drtinaz/mp2_emulator
   
   (installs a multiplus 2 emulator)

   
```
wget -O /tmp/download.py https://raw.githubusercontent.com/drtinaz/scripts/main/download.py
python /tmp/download.py
```
