from operator import attrgetter

from powdeviceinfo.cfgmgr import CMSetupClass

for cls in sorted(CMSetupClass.iter(), key=attrgetter("classname_or_none")):
    print((cls.guid, cls.classname_or_none, cls.name_or_none))
