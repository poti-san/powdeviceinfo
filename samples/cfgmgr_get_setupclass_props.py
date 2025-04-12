from powdeviceinfo.cfgmgr import CMSetupClass

classes = tuple(CMSetupClass.iter())
for prop in classes[0].props:
    print((prop.key, prop))
