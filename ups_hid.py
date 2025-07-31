# overrides of hid.py to implement additional features for UPS descriptor

import usb.device
import struct, time
from usb.device.hid import HIDInterface
from usb.device.core import split_bmRequestType
#from UPSDescriptor import _UPS_REPORT_DESC
#from UPS_Report_Descriptor import *
#from UPSReportDescriptor2 import _UPS_REPORT_DESC
import ups

_EP_IN_FLAG = const(1 << 7)

# Control transfer stages
_STAGE_IDLE = const(0)
_STAGE_SETUP = const(1)
_STAGE_DATA = const(2)
_STAGE_ACK = const(3)

# Request types
_REQ_TYPE_STANDARD = const(0x0)
_REQ_TYPE_CLASS = const(0x1)
_REQ_TYPE_VENDOR = const(0x2)
_REQ_TYPE_RESERVED = const(0x3)

# Descriptor types
_DESC_HID_TYPE = const(0x21)
_DESC_REPORT_TYPE = const(0x22)
_DESC_PHYSICAL_TYPE = const(0x23)

# Interface and protocol identifiers
_INTERFACE_CLASS = const(0x03)
_INTERFACE_SUBCLASS_NONE = const(0x00)
_INTERFACE_SUBCLASS_BOOT = const(0x01)

_INTERFACE_PROTOCOL_NONE = const(0x00)
_INTERFACE_PROTOCOL_KEYBOARD = const(0x01)
_INTERFACE_PROTOCOL_MOUSE = const(0x02)

# bRequest values for HID control requests
_REQ_CONTROL_GET_REPORT = const(0x01)
_REQ_CONTROL_GET_IDLE = const(0x02)
_REQ_CONTROL_GET_PROTOCOL = const(0x03)
_REQ_CONTROL_GET_DESCRIPTOR = const(0x06)
_REQ_CONTROL_SET_REPORT = const(0x09)
_REQ_CONTROL_SET_IDLE = const(0x0A)
_REQ_CONTROL_SET_PROTOCOL = const(0x0B)

# Standard descriptor lengths
_STD_DESC_INTERFACE_LEN = const(9)
_STD_DESC_ENDPOINT_LEN = const(7)

# bRequest values for HID control requests
_REPORT_TYPE_INPUT = const(0x01)
_REPORT_TYPE_OUTPUT = const(0x02)
_REPORT_TYPE_FEATURE = const(0x03)

#PWR_STAT = 0b1101 #batt, AC, discharge, charge
#PWR_STAT = 0b1010 #reversed

# default values
dft = {
  'batt_lvl': 80,                   # current battery capacity
  'pwr_stat': 0b1101,
  'pwr_stat2': 0,
  'stat': bytearray([0b1101, 0]),
  'secs_remain': 8220,
  'batt_v': 12.0,                   # current battery Voltage
  # 
  'iProduct': 2,
  'iSerialNumber': 3,
  'iManufacturer': 1,
  'Rechargable': 1,
  'ManufactureDate': {'y': 2025, 'm': 5, 'd': 30},
  'ConfigVoltage': 12.8,            # nominal batt voltage
  'FullChargeCapacity': 100,        # (%)
  'WarningCapacityLimit': 10,       # (%)
  'CapacityGranularity1': 1,        # todo: check this
  'RemainingCapacityLimit': 5,      # (%)
  'DelayBeforeShutdown': -1,
  'DelayBeforeReboot': -1,
  'CapacityMode': 2,             # =%# todo: check this for mwH
  'DesignCapacity': 100,            # %
  'CapacityGranularity2': 1,        # todo: check this
  'AverageTimeToFull': 21600,       # (secs)=6 hours
  'AverageTimeToEmpty': 3600,       # (secs)= 1 hour
  'iDeviceChemistry': 4,            # (index)
  'iDeviceChemistryStr': "SLA"
}

class UPSHIDInterface(HIDInterface):
    #missing_reps = ""
    #def __init__(self, *args, **kwargs):
    #    super().__init__(*args, **kwargs)
    def __init__(
            self,
            report_descriptor,
            extra_descriptors=[],
            set_report_buf=None,
            protocol=_INTERFACE_PROTOCOL_NONE,
            interface_str=None,
            additional_strs=None,
            features=None
        ):
        super().__init__(
            report_descriptor,
            extra_descriptors,
            set_report_buf,
            protocol,
            interface_str,
        )
        # set some initial values
        self.additional_strs = additional_strs
        self.battery_volts = 12.8
        self.battery_level = dft.get("batt_lvl", 75) #88  # Default UPS battery % for feature report
        #self.batt_date = features.get("batt_date", {'y': 2025, 'm': 5, 'd': 30})
        self.pwr_stat = 0b1101 # batt, AC, discharging, charging
        #self.pwr_stat = 0b1010 # running on batt
        self.pwr_stat2 = 0
        self.status_flags = bytearray([self.pwr_stat, self.pwr_stat2])
        self.secs_remain = 8220
        
        self.iProduct = features.get('iProduct', dft['iProduct'])
        self.iSerialNumber = features.get('iSerialNumber', dft['iSerialNumber'])
        self.iManufacturer = features.get('iManufacturer', dft['iManufacturer'])
        self.Rechargable = features.get('Rechargable', dft['Rechargable'])
        #todo: set date to a value in a static method
        self.ManufactureDate = features.get('ManufactureDate', dft['ManufactureDate'])
        self.ConfigVoltage = features.get('ConfigVoltage', dft['ConfigVoltage'])
        self.FullChargeCapacity = features.get('FullChargeCapacity', dft['FullChargeCapacity'])
        self.WarningCapacityLimit = features.get('WarningCapacityLimit', dft['WarningCapacityLimit'])
        self.CapacityGranularity1 = features.get('CapacityGranularity1', dft['CapacityGranularity1'])
        self.RemainingCapacityLimit = features.get('RemainingCapacityLimit', dft['RemainingCapacityLimit'])
        self.DelayBeforeShutdown = features.get('DelayBeforeShutdown', dft['DelayBeforeShutdown'])
        self.DelayBeforeReboot = features.get('DelayBeforeReboot', dft['DelayBeforeReboot'])
        #alarm control
        self.CapacityMode = features.get('CapacityMode', dft['CapacityMode'])
        self.DesignCapacity = features.get('DesignCapacity', dft['DesignCapacity'])
        self.CapacityGranularity2 = features.get('CapacityGranularity2', dft['CapacityGranularity2'])
        self.AverageTimeToFull = features.get('AverageTimeToFull', dft['AverageTimeToFull'])
        self.AverageTimeToEmpty = features.get('AverageTimeToEmpty', dft['AverageTimeToEmpty'])
        self.iDeviceChemistry = features.get('iDeviceChemistry', dft['iDeviceChemistry'])
        self.iDeviceChemistryStr = features.get('iDeviceChemistryStr', dft['iDeviceChemistryStr'])

    
    def on_interface_control_xfer(self, stage, request):
        # Handle standard and class-specific interface control transfers for HID devices.
        # added a handler for detaure reports
        bmRequestType, bRequest, wValue, wIndex, wLength = struct.unpack("BBHHH", request)

        recipient, req_type, _ = split_bmRequestType(bmRequestType)
        if stage == _STAGE_SETUP:
            if req_type == _REQ_TYPE_STANDARD:
                # HID Spec p48: 7.1 Standard Requests
                if bRequest == _REQ_CONTROL_GET_DESCRIPTOR:
                    desc_type = wValue >> 8
                    #print(f"{desc_type=}")
                    if desc_type == _DESC_HID_TYPE:
                        return self.get_hid_descriptor()
                    if desc_type == _DESC_REPORT_TYPE:
                        return self.report_descriptor
                    #if desc_type == 3: # STRING (0x03)
                    #    str_idx = wValue & 0xFF
                    #    print(f"{str_idx=}")
                    #    return self._send_str_descriptor(str_idx)
            elif req_type == _REQ_TYPE_CLASS:
                # HID Spec p50: 7.2 Class-Specific Requests
                if bRequest == _REQ_CONTROL_GET_REPORT:
                    #handle get feature requests
                    #return False  # Unsupported for now
                    # Handle GET_REPORT (0x01), Report Type 3 = Feature 
                    report_type = wValue >> 8
                    report_id = wValue & 0xFF
                    if bRequest == _REQ_CONTROL_GET_REPORT and report_type == _REPORT_TYPE_FEATURE:
                        return self._on_get_feature_handler(report_id)
                    else:
                        return False  # Unsupported request
                    
                if bRequest == _REQ_CONTROL_GET_IDLE:
                    return bytes([self.idle_rate])
                if bRequest == _REQ_CONTROL_GET_PROTOCOL:
                    return bytes([self.protocol])
                if bRequest in (_REQ_CONTROL_SET_IDLE, _REQ_CONTROL_SET_PROTOCOL):
                    return True
                if bRequest == _REQ_CONTROL_SET_REPORT:
                    return self._set_report_buf  # If None, request will stall
            return False  # Unsupported request

        if stage == _STAGE_ACK:
            if req_type == _REQ_TYPE_CLASS:
                if bRequest == _REQ_CONTROL_SET_IDLE:
                    self.idle_rate = wValue >> 8
                elif bRequest == _REQ_CONTROL_SET_PROTOCOL:
                    self.protocol = wValue
                elif bRequest == _REQ_CONTROL_SET_REPORT:
                    report_id = wValue & 0xFF
                    report_type = wValue >> 8
                    report_data = self._set_report_buf
                    if wLength < len(report_data):
                        # need to truncate the response in the callback if we got less bytes
                        # than allowed for in the buffer
                        report_data = memoryview(self._set_report_buf)[:wLength]
                    self.on_set_report(report_data, report_id, report_type)

        return True  # allow DATA/ACK stages to complete normally
    
    def _on_get_feature_handler(self, report_id):
        # handle get feature reports
        # override this to return feature reports to the host
        #return False
        # todo: change this from elif series to 
        # todo: change report numbers to names
        '''data = None
        if report_id == 1:
            # iProduct str
            data = bytearray([2])
        elif report_id == 2:
            # iSerialNumber str
            data = bytearray([3])
        elif report_id == 3:
            # iManufacturer str
            data = bytearray([1])
        elif report_id == 6:
            # Rechargable 0/1
            data = bytearray([1])
        elif report_id == 7:
            # present status
            data = bytearray([PWR_STAT, PWR_STAT_2])
        elif report_id == 8:
            # RemainingTimeLimit 120-1380
            data = struct.pack('<H', 480)
        elif report_id == 9:
            # Manufacture Date
            # todo: APC uses a different format according to NUT - add some logic here
            year, month, day = 2025, 5, 19
            # from 4.2.6 Battery Settings in "Universal Serial Bus Usage Tables for HID Power Devices"
            data = struct.pack('<H', ((year - 1980)*512 + month*32 + day))
        elif report_id == 10:
            # ConfigVoltage centivolts
            data = struct.pack('<H', 1380)
        elif report_id == 11:
            # voltage
            data = struct.pack('<H', 1300)
        elif report_id == 12:
            # battery level
            data = bytearray([self._battery_level])
        elif report_id == 13:
            # runtime to empty (secs)
            data = struct.pack('<H', 8220)
        elif report_id == 14:
            # FullChargeCapacity
            data = bytearray([100])
        elif report_id == 15:
            # warning capacity limit %
            data = bytearray([10])
        elif report_id == 16:
            # CapacityGranularity1
            data = bytearray([1])
        elif report_id == 17:
            # RemainingCapacityLimit %
            data = bytearray([5])
        elif report_id == 18:
            # DelayBeforeShutdown -32768 to 32767
            data = struct.pack('<H', -1)#32767) # -1?
        elif report_id == 19:
            # DelayBeforeReboot -32768 to 32767
            data = struct.pack('<H', -1)#32767) # -1?
        elif report_id == 20:
            # Audible Alarm Control 1 - Disabled, 2 - Enabled, 3 - Muted
            data = bytearray([1])
        elif report_id == 22:
            # Capacity Mode %age
            data = bytearray([2])
        elif report_id == 23:
            # DesignCapacity
            data = bytearray([100])
        elif report_id == 24:
            # CapacityGranularity2
            data = bytearray([1])
        elif report_id == 26:
            # AverageTimeToFull
            data = struct.pack('<H', 8220)
        elif report_id == 28:
            # AverageTimeToEmpty
            data = struct.pack('<H', 8220)
        elif report_id == 31:
            # iDeviceChemistry str idx
            data = bytearray([4]) # index of string in device strings
        elif report_id == 32:
            # iOEMInformation str idx
            data = bytearray([5]) # ndex of string in device strings
        else:
            print(f"{report_id=} not implementeded")
            return False
        if data:
            result = bytearray([report_id])
            result.extend(data)
        else:
            print(f"{report_id=} not implementeded")
            result = False
        return result'''
        # Mapping of report_id to their respective handlers
        # Lazy evaluation: Lambdas delay the evaluation until the handler is called, which allows use of dynamic values like self._battery_level.
        # also Lanbdas are cabllable
        handlers = {
            #ups.HID_PD_IPRODUCT: lambda: bytearray([2]),                         # iProduct str
            #ups.HID_PD_SERIAL: lambda: bytearray([3]),                         # iSerialNumber str
            #ups.HID_PD_MANUFACTURER: lambda: bytearray([1]),                         # iManufacturer str
            #ups.HID_PD_RECHARGEABLE: lambda: bytearray([1]),                         # Rechargable
            1: lambda: bytearray([2]),                         # iProduct str
            2: lambda: bytearray([3]),                         # iSerialNumber str
            3: lambda: bytearray([1]),                         # iManufacturer str
            6: lambda: bytearray([1]),                         # Rechargable
            7: lambda: bytearray([self.pwr_stat, self.pwr_stat2]), # present status
            8: lambda: struct.pack('<H', 480),                 # RemainingTimeLimit
            9: lambda: struct.pack('<H', ((self.ManufactureDate['y'] - 1980)*512 + self.ManufactureDate['m']*32 + self.ManufactureDate['d'])),  # Manufacture Date
            #9: lambda: struct.pack('<H', ((2025 - 1980)*512 + 5*32 + 25)),
            10: lambda: struct.pack('<H', 1280),               # ConfigVoltage
            11: lambda: struct.pack('<H', 1350),               # Voltage
            12: lambda: bytearray([self.battery_level]),       # Battery Level
            13: lambda: struct.pack('<H', self.secs_remain),   # Runtime to empty
            14: lambda: bytearray([100]),                      # FullChargeCapacity
            15: lambda: bytearray([10]),                       # Warning capacity limit
            16: lambda: bytearray([1]),                        # CapacityGranularity1
            17: lambda: bytearray([5]),                        # RemainingCapacityLimit
            18: lambda: struct.pack('<H', -1),                 # DelayBeforeShutdown
            19: lambda: struct.pack('<H', -1),                 # DelayBeforeReboot
            20: lambda: bytearray([1]),                        # Audible Alarm Control
            22: lambda: bytearray([2]),                        # Capacity Mode
            23: lambda: bytearray([100]),                      # DesignCapacity
            24: lambda: bytearray([1]),                        # CapacityGranularity2
            26: lambda: struct.pack('<H', 8220),               # AverageTimeToFull
            28: lambda: struct.pack('<H', 8220),               # AverageTimeToEmpty
            31: lambda: bytearray([4]),                        # iDeviceChemistry
            32: lambda: bytearray([5]),                        # iOEMInformation
        }
        # todo: make handlers a property so it is not constantly recreated
        print(f"{report_id=} requested")
        handler = handlers.get(report_id)
        if handler:
            data = handler()
            return bytearray([report_id]) + data
        else:
            print(f"{report_id=} not implemented")
            return False

    def desc_cfg(self, desc, itf_num, ep_num, strs):
        # Add the standard interface descriptor
        # using extend allows us to pass in a list
        # todo: testing .extend
        # todo: how to flag if we do want an interface string?
        # currently is set to index 0 = None
        # previously was set to 1st non-standard string descriptor
        # 
        desc.interface(
            itf_num,
            1,
            _INTERFACE_CLASS,
            _INTERFACE_SUBCLASS_NONE,
            self.protocol,
            len(strs) if self.interface_str else 0, # strInterface index (if used)
            # Note that iInterface is a string index number. 
        )

        if self.interface_str:
            strs.append(self.interface_str)
            
        # add any additional string descriptors
        # you will need to manage the indexes manually
        # ie 1st additional_str will be index 4 if interface_str is not used, otherwise 5
        if self.additional_strs:
            if isinstance(self.additional_strs, (list, tuple)):
                strs.extend(self.additional_strs)
            else:
                strs.append(self.additional_strs)

        # As per HID v1.11 section 7.1 Standard Requests, return the contents of
        # the standard HID descriptor before the associated endpoint descriptor.
        self.get_hid_descriptor(desc)

        # Add the typical single USB interrupt endpoint descriptor associated
        # with a HID interface.
        self._int_ep = ep_num | _EP_IN_FLAG
        desc.endpoint(self._int_ep, "interrupt", 8, 8)

        self.idle_rate = 0
        self.protocol = 0

class PresentStatus:
    _bit_names = [
        "charging",
        "discharging",
        "ac_present",
        "battery_present",
        "below_capacity_limit",
        "time_limit_expired",
        "need_replacement",
        "voltage_not_regulated",
        "fully_charged",
        "fully_discharged",
        "shutdown_requested",
        "shutdown_imminent",
        "communication_lost",
        "overload",
        "unused1",
        "unused2",
    ]

    def __init__(self, value=0):
        self._value = value

    def _get_bit(self, pos):
        return bool((self._value >> pos) & 1)

    def _set_bit(self, pos, val):
        if val:
            self._value |= (1 << pos)
        else:
            self._value &= ~(1 << pos)

    def to_uint16(self):
        return self._value

    def from_uint16(self, value):
        self._value = value

# Dynamically add properties for each bit
for i, name in enumerate(PresentStatus._bit_names):
    getter = lambda self, i=i: self._get_bit(i)
    setter = lambda self, val, i=i: self._set_bit(i, val)
    setattr(PresentStatus, name, property(getter, setter))
'''
ps = PresentStatus()
ps.charging = True
ps.ac_present = True
ps.shutdown_imminent = True

print(bin(ps.to_uint16()))  # e.g. 0b10000101'''