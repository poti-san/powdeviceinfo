from powdeviceinfo.cfgmgr import CMDevice

for device in CMDevice.iter_all(True):
    print((device.devinst, device.name_or_none, device.description_or_none))
