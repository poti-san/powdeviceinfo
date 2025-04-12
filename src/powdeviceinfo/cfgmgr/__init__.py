from abc import abstractmethod
from ctypes import (
    POINTER,
    Array,
    byref,
    c_byte,
    c_int32,
    c_uint32,
    c_void_p,
    c_wchar,
    c_wchar_p,
)
from enum import IntFlag
from typing import Iterator, OrderedDict, Self, override

from powguid import Guid

from .. import _cfgmgr32
from ..devprop import (
    DeviceClassPropertyKeys,
    DeviceProperty,
    DevicePropertyKey,
    DevicePropertyKeys,
    DevicePropertyType,
)
from .crresult import CR_BUFFER_SMALL, CR_NO_SUCH_VALUE, CR_SUCCESS


class CMError(Exception):
    cr: int

    def __init__(self, cr: int) -> None:
        self.cr = cr

    @staticmethod
    def throw_if_failed(cr: int) -> None:
        if cr != CR_SUCCESS:
            raise CMError(cr)

    @staticmethod
    def throw_ifnot_buffersmall(cr: int) -> None:
        if cr != CR_BUFFER_SMALL:
            raise CMError(cr)


class CMEnumerator:
    __slots__ = ()

    @staticmethod
    def iter() -> Iterator[Guid]:
        MAX_DEVICE_ID_LEN = 200
        buf = (c_wchar * MAX_DEVICE_ID_LEN)()
        buflen = c_uint32()
        for i in range(0xFFFFFFFF):
            buflen.value = MAX_DEVICE_ID_LEN
            cr = _CM_Enumerate_EnumeratorsW(i, buf, byref(buflen), 0)
            if cr == CR_NO_SUCH_VALUE:
                return
            yield buf.value
        raise OverflowError


class CMClass:
    __slots__ = ("_guid",)
    _guid: Guid

    def __init__(self, guid: Guid) -> None:
        self._guid = guid

    @property
    def guid(self) -> Guid:
        """Guidの複製を返します。"""
        return Guid.from_buffer_copy(self._guid)

    @staticmethod
    @abstractmethod
    def classenumflags() -> int: ...

    @staticmethod
    @abstractmethod
    def classpropflags() -> int: ...

    @classmethod
    def iter(cls) -> "Iterator[Self]":
        flags = cls.classenumflags()
        for i in range(0xFFFFFFFF):
            guid = Guid()  # 使いまわすと作成したインスタンスのguidがすべて変わります。
            cr = _CM_Enumerate_Classes(i, byref(guid), flags)
            if cr == CR_NO_SUCH_VALUE:
                return
            yield cls(guid)
        raise OverflowError

    @property
    def propkeycount(self) -> int:
        flags = self.classpropflags()

        c = c_uint32()
        cr = _CM_Get_Class_Property_Keys(self._guid, None, byref(c), flags)
        if cr == CR_SUCCESS or cr == CR_BUFFER_SMALL:
            return c.value
        else:
            raise CMError(cr)

    @property
    def propkeys(self) -> tuple[DevicePropertyKey, ...]:
        flags = self.classpropflags()

        c = c_uint32()
        cr = _CM_Get_Class_Property_Keys(self._guid, None, byref(c), flags)
        if cr == CR_SUCCESS:
            return ()
        elif cr != CR_BUFFER_SMALL:
            raise CMError(cr)

        keys = (DevicePropertyKey * c.value)()
        cr = _CM_Get_Class_Property_Keys(self._guid, keys, byref(c), flags)
        if cr != CR_SUCCESS:
            raise CMError(cr)
        return tuple(keys)

    def get_prop(self, key: DevicePropertyKey) -> DeviceProperty:
        flags = self.classpropflags()

        type = c_int32()
        bufsize = c_uint32()
        CMError.throw_ifnot_buffersmall(
            _CM_Get_Class_PropertyW(self._guid, key, byref(type), None, byref(bufsize), flags)
        )

        buf = (c_byte * bufsize.value)()
        CMError.throw_if_failed(_CM_Get_Class_PropertyW(self._guid, key, byref(type), buf, byref(bufsize), flags))

        return DeviceProperty(key, DevicePropertyType(type.value), bytes(buf))

    def get_prop_or_none(self, key: DevicePropertyKey) -> DeviceProperty | None:
        flags = self.classpropflags()

        type = c_int32()
        bufsize = c_uint32()
        cr = _CM_Get_Class_PropertyW(self._guid, key, byref(type), None, byref(bufsize), flags)
        if cr != CR_BUFFER_SMALL:
            return None

        buf = (c_byte * bufsize.value)()
        cr = _CM_Get_Class_PropertyW(self._guid, key, byref(type), buf, byref(bufsize), flags)
        if cr != CR_SUCCESS:
            return None

        return DeviceProperty(key, DevicePropertyType(type.value), bytes(buf))

    @property
    def props(self) -> tuple[DeviceProperty, ...]:
        return tuple(self.get_prop(key) for key in self.propkeys)

    @property
    def name_or_none(self) -> str | None:
        prop = self.get_prop_or_none(DevicePropertyKeys.NAME)
        return prop.str_or_none if prop else None

    @property
    def instanceid_or_none(self) -> str | None:
        prop = self.get_prop_or_none(DevicePropertyKeys.INSTANCE_ID)
        return prop.str_or_none if prop else None


class CMSetupClass(CMClass):
    __slots__ = ()

    @override
    @staticmethod
    def classenumflags() -> int:
        CM_ENUMERATE_CLASSES_INSTALLER = 0x00000000
        return CM_ENUMERATE_CLASSES_INSTALLER

    @override
    @staticmethod
    def classpropflags() -> int:
        CM_CLASS_PROPERTY_INSTALLER = 0x00000000
        return CM_CLASS_PROPERTY_INSTALLER

    @property
    def classname_or_none(self) -> str | None:
        prop = self.get_prop_or_none(DeviceClassPropertyKeys.CLASS_NAME)
        return prop.str_or_none if prop else None

    @staticmethod
    def find_by_classname(classname: str, ignorecase: bool) -> "CMSetupClass | None":
        if not ignorecase:
            for cls in CMSetupClass.iter():
                if cls.classname_or_none == classname:
                    return cls
            return None
        else:
            classname = str(classname).lower()
            for cls in CMSetupClass.iter():
                clsname = cls.classname_or_none
                if clsname is not None and clsname.lower() == classname:
                    return cls
            return None


class CMInterfaceClass(CMClass):
    __slots__ = ()

    @override
    @staticmethod
    def classenumflags() -> int:
        CM_ENUMERATE_CLASSES_INTERFACE = 0x00000001
        return CM_ENUMERATE_CLASSES_INTERFACE

    @override
    @staticmethod
    def classpropflags() -> int:
        CM_CLASS_PROPERTY_INTERFACE = 0x00000001
        return CM_CLASS_PROPERTY_INTERFACE


class CMLocateFlag(IntFlag):
    NORMAL = 0x00000000
    PHANTOM = 0x00000001
    CANCEL_REMOVE = 0x00000002
    NO_VALIDATION = 0x00000004


class CMDeviceID:
    __slots__ = ()

    @staticmethod
    def __getdeviceidlist_worker(filter: str | None, flags: int, presents_only: bool) -> list[str]:
        CM_GETIDLIST_FILTER_PRESENT = 0x00000100
        if presents_only:
            flags |= CM_GETIDLIST_FILTER_PRESENT

        cb = c_uint32()
        CMError.throw_if_failed(_CM_Get_Device_ID_List_SizeW(byref(cb), filter, flags))

        len = cb.value
        buf = (c_wchar * len)()
        CMError.throw_if_failed(_CM_Get_Device_ID_ListW(filter, buf, len, flags))
        return bytes(buf)[:-4].decode("utf-16le").split("\0")

    @staticmethod
    def iter_all(presents_only: bool = False) -> Iterator[str]:
        CM_GETIDLIST_FILTER_NONE = 0x00000000
        yield from CMDeviceID.__getdeviceidlist_worker(None, CM_GETIDLIST_FILTER_NONE, presents_only)

    @staticmethod
    def iter_by_enumerator(enumerator: str, presents_only: bool) -> Iterator[str]:
        CM_GETIDLIST_FILTER_ENUMERATOR = 0x00000001
        yield from CMDeviceID.__getdeviceidlist_worker(enumerator, CM_GETIDLIST_FILTER_ENUMERATOR, presents_only)

    @staticmethod
    def iter_by_class(enumerator: str, presents_only: bool) -> Iterator[str]:
        CM_GETIDLIST_FILTER_CLASS = 0x00000200
        yield from CMDeviceID.__getdeviceidlist_worker(enumerator, CM_GETIDLIST_FILTER_CLASS, presents_only)


class CMDevice:
    __slots__ = ("__devinst",)
    __devinst: int

    def __init__(self, id: str, flags: CMLocateFlag | int = CMLocateFlag.NORMAL) -> None:
        x = c_int32()
        CMError.throw_if_failed(_CM_Locate_DevNodeW(byref(x), id, int(flags)))
        self.__devinst = x.value

    @property
    def devinst(self) -> int:
        return self.__devinst

    @staticmethod
    def iter_all(presents_only: bool = False) -> Iterator["CMDevice"]:
        return (CMDevice(id) for id in CMDeviceID.iter_all(presents_only))

    @staticmethod
    def iter_deviceid_by_enumerator(enumerator: str, presents_only: bool) -> Iterator["CMDevice"]:
        return (CMDevice(id) for id in CMDeviceID.iter_by_enumerator(enumerator, presents_only))

    @staticmethod
    def iter_deviceid_by_classid(classid: str, presents_only: bool) -> Iterator["CMDevice"]:
        return (CMDevice(id) for id in CMDeviceID.iter_by_class(classid, presents_only))

    @staticmethod
    def iter_deviceid_by_classguid(classguid: Guid, presents_only: bool) -> Iterator["CMDevice"]:
        return (CMDevice(id) for id in CMDeviceID.iter_by_class(str(classguid), presents_only))

    @staticmethod
    def iter_deviceid_by_class(class_: CMSetupClass, presents_only: bool) -> Iterator["CMDevice"]:
        return CMDevice.iter_deviceid_by_classguid(class_.guid, presents_only)

    @staticmethod
    def iter_deviceid_by_classname(
        classname: str, presents_only: bool, ignorecase: bool = True
    ) -> Iterator["CMDevice"]:
        class_ = CMSetupClass.find_by_classname(classname, ignorecase)
        if class_ is None:
            raise ValueError
        return CMDevice.iter_deviceid_by_class(class_, presents_only)

    @property
    def propkeyscount(self) -> int:
        c = c_uint32()
        CMError.throw_ifnot_buffersmall(_CM_Get_DevNode_Property_Keys(self.__devinst, None, byref(c), 0))
        return c.value

    @property
    def propkeys(self) -> tuple[DevicePropertyKey, ...]:
        c = c_uint32()
        CMError.throw_ifnot_buffersmall(_CM_Get_DevNode_Property_Keys(self.__devinst, None, byref(c), 0))

        keys = (DevicePropertyKey * c.value)()
        CMError.throw_if_failed(_CM_Get_DevNode_Property_Keys(self.__devinst, keys, byref(c), 0))
        return tuple(keys)

    def get_prop(self, key: DevicePropertyKey) -> DeviceProperty:
        type = c_int32()
        size = c_uint32()
        CMError.throw_ifnot_buffersmall(
            _CM_Get_DevNode_PropertyW(self.__devinst, key, byref(type), None, byref(size), 0)
        )

        buf: Array[c_byte] = (c_byte * size.value)()
        CMError.throw_if_failed(_CM_Get_DevNode_PropertyW(self.__devinst, key, byref(type), buf, byref(size), 0))
        return DeviceProperty(key, DevicePropertyType(type.value), bytes(buf))

    def get_prop_or_none(self, key: DevicePropertyKey) -> DeviceProperty | None:
        type = c_int32()
        size = c_uint32()
        cr = _CM_Get_DevNode_PropertyW(self.__devinst, key, byref(type), None, byref(size), 0)
        if cr != CR_BUFFER_SMALL:
            return None

        buf: Array[c_byte] = (c_byte * size.value)()
        cr = _CM_Get_DevNode_PropertyW(self.__devinst, key, byref(type), buf, byref(size), 0)
        if cr != CR_SUCCESS:
            return None
        return DeviceProperty(key, DevicePropertyType(type.value), bytes(buf))

    @property
    def name_or_none(self) -> str | None:
        prop = self.get_prop(DevicePropertyKeys.NAME)
        return prop.str_or_none if prop else None

    @property
    def instanceid_or_none(self) -> str | None:
        prop = self.get_prop(DevicePropertyKeys.INSTANCE_ID)
        return prop.str_or_none if prop else None

    @property
    def description_or_none(self) -> str | None:
        prop = self.get_prop(DevicePropertyKeys.DEVICE_DESC)
        return prop.str_or_none if prop else None

    @property
    def props_iter(self) -> Iterator[tuple[DevicePropertyKey, DeviceProperty]]:
        get_prop = self.get_prop
        return ((key, get_prop(key)) for key in self.propkeys)

    @property
    def props(self) -> tuple[tuple[DevicePropertyKey, DeviceProperty], ...]:
        return tuple(self.props_iter)

    @property
    def propdict(self) -> OrderedDict[DevicePropertyKey, DeviceProperty]:
        return OrderedDict(self.props_iter)


_CM_Enumerate_EnumeratorsW = _cfgmgr32.CM_Enumerate_EnumeratorsW
_CM_Enumerate_EnumeratorsW.argtypes = (c_uint32, c_wchar_p, POINTER(c_uint32), c_uint32)

_CM_Enumerate_Classes = _cfgmgr32.CM_Enumerate_Classes
_CM_Enumerate_Classes.argtypes = (c_uint32, POINTER(Guid), c_uint32)

_CM_Get_Class_Property_Keys = _cfgmgr32.CM_Get_Class_Property_Keys
_CM_Get_Class_Property_Keys.argtypes = (POINTER(Guid), POINTER(DevicePropertyKey), POINTER(c_uint32), c_uint32)

_CM_Get_Class_PropertyW = _cfgmgr32.CM_Get_Class_PropertyW
_CM_Get_Class_PropertyW.argtypes = (
    POINTER(Guid),
    POINTER(DevicePropertyKey),
    POINTER(c_int32),
    c_void_p,
    POINTER(c_uint32),
    c_uint32,
)

_CM_Get_Device_ID_List_SizeW = _cfgmgr32.CM_Get_Device_ID_List_SizeW
_CM_Get_Device_ID_List_SizeW.argtypes = (POINTER(c_uint32), c_wchar_p, c_uint32)

_CM_Get_Device_ID_ListW = _cfgmgr32.CM_Get_Device_ID_ListW
_CM_Get_Device_ID_ListW.argtypes = (c_wchar_p, c_wchar_p, c_uint32, c_uint32)

_CM_Locate_DevNodeW = _cfgmgr32.CM_Locate_DevNodeW
_CM_Locate_DevNodeW.argtypes = (POINTER(c_int32), c_wchar_p, c_uint32)

_CM_Get_DevNode_Property_Keys = _cfgmgr32.CM_Get_DevNode_Property_Keys
_CM_Get_DevNode_Property_Keys.argtypes = (c_int32, POINTER(DevicePropertyKey), POINTER(c_uint32), c_uint32)

_CM_Get_DevNode_PropertyW = _cfgmgr32.CM_Get_DevNode_PropertyW
_CM_Get_DevNode_PropertyW.argtypes = (
    c_int32,
    POINTER(DevicePropertyKey),
    POINTER(c_int32),
    c_void_p,
    POINTER(c_uint32),
    c_uint32,
)
