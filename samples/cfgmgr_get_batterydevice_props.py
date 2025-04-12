from powdeviceinfo.cfgmgr import CMDevice

for device in CMDevice.iter_deviceid_by_classname("battery", True):
    print((device.devinst, device.name_or_none, device.instanceid_or_none))
