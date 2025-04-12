from powdeviceinfo.cfgmgr import CMInterfaceClass

for cls in CMInterfaceClass.iter():
    print((cls.guid, cls.name_or_none))
