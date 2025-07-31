# todo: logic around charging bit ie 0 if @ 100%
#

import usb.device
from ups_hid import UPSHIDInterface
import ups
import time, struct
#from UPS_Report_Descriptor import * # todo: can we avoid import *?

#additional interface strings, iDeviceChemistry, iOEMInformation]
#interface_strs = ["itf str here", "Lead-Acid SLA", "OEM info here"]
addntl_strs = ["Lead-Acid SLA2", "OEM info here"]
#interface_strs = "test itf str"

#set feature options to override defaults
feature_vals = {
  "batt_lvl": 80,
  "pwr_stat": 0b1101,
  "pwr_stat2": 0,
  "stat": bytearray([0b1101, 0]),
  "secs_remain": 8220,
}
# iProduct str 2
# iSerialNumber str 3
# iManufacturer str 1
# Rechargable 1
# Manufacture Date {'y': 2025, 'm': 5, 'd': 30}
# ConfigVoltage 12.8
# FullChargeCapacity 100(%)
# Warning capacity limit  10(%)
# CapacityGranularity1 =1
# RemainingCapacityLimit 5(%)
# DelayBeforeShutdown -1
# DelayBeforeReboot -1
# Capacity Mode 2=%
# DesignCapacity 100%
# CapacityGranularity2 =1
# AverageTimeToFull 21600(secs)=6 hours
# AverageTimeToEmpty 3600(secs)= 1 hour
# iDeviceChemistry 4(index)
# iDeviceChemistryStr "Pb-Ac SLA"

# Create the HID interface with a feature report
# todo: pass a load of features here, ie runtimetoempty, all the feature/input report initial values
def startup(cdc_en=True):
    dev = UPSHIDInterface(
                ups._UPS_REPORT_DESC,
                #set_report_buf=bytearray(16), #todo: reduce this to 4?
                #protocol= 0, #ups_hid._INTERFACE_PROTOCOL_NONE,
                # interface_str=interface_strs,
                additional_strs=addntl_strs,
                features=feature_vals,
    )

    #print("ups init")


    # set artificial vendor & product id's so NUT sees this as an APC UPS
    usb.device.get().init(dev, builtin_driver=cdc_en, # change to False after testing
                                manufacturer_str="British Power Conversion",
                                product_str="Back-UPS BK650M2-CH FW:v17_294803G -292804G", # todo: check & test how/if NUT uses these
                                serial_str="9B2334A45622",
                                #id_vendor=0x051D, #emulate APC UPS
                                #id_product=2, #works with 3, but driver disables inputs
                                #bcd_device=0x0100, seems to break things
                                max_power_ma=60) # 60todo: limit this further?

    while not dev.is_open():
        time.sleep_ms(100)


    c = 0


    # todo: bit comparison for power fail
    # todo: timers to send reports?
    # todo: use constants for report names
    # todo: add battery charging info if AC present
    # todo: move to hardware testing of AC & batterty state
    while True:
        #
        if dev.pwr_stat == 0b1010: # power fail condition
            data = struct.pack('<BB', ups.HID_PD_REMAININGCAPACITY, dev.battery_level)
            dev.send_report(data)
            time.sleep(0.1)
            data = struct.pack('<BH', ups.HID_PD_RUNTIMETOEMPTY , dev.secs_remain)
            dev.send_report(data)
                  
            dev.secs_remain -= 1
            
            data = struct.pack('<BH', ups.HID_PD_PRESENTSTATUS, dev.pwr_stat, dev.pwr_stat2) 
            dev.send_report(data)
            if c % 60 == 0:
                dev.battery_level -= 1
                # decrement 1% off battery every minute
        c+=1
        if dev.pwr_stat == 0b1101:
            # AC present, charging
            if c % 60 == 0:
                dev.battery_level += 1
                # increment 1% to battery every minute
            if dev.battery_level >= 100:
                dev.battery_level = 100
                dev.pwr_stat == 0b1100

        if c== 300: #3600: #after an hour simulate power fail15:
            dev.pwr_stat = 0b1010 # on batt 
            #PWR_STAT = 0b0101 reverses  - appears ac on but no batt
            #print('pwr off')
        if c== 600: # 7200: # after an hour on battery, simulate power resumed 30:
            dev.pwr_stat = 0b1101 # power on batt not detected
            #PWR_STAT = 0b1011 appears on batt
            #print('pwr on')
            c = 0
        time.sleep(0.7)


if __name__ == '__main__':
    #start with CDC enabled, mostly seems to stop device from working
    startup()