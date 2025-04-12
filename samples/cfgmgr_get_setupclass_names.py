from pprint import pp

from powdeviceinfo.cfgmgr import CMSetupClass

pp(sorted(cls.classname_or_none or "" for cls in CMSetupClass.iter()))
