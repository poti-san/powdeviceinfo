from abc import abstractmethod
from ctypes import (
    POINTER,
    WinDLL,
    byref,
    c_byte,
    c_int32,
    c_uint32,
    c_void_p,
    c_wchar,
    c_wchar_p,
)
from typing import Iterator, Self, override

from powguid import Guid

from ..devprop import DeviceProperty, DevicePropertyKey, DevicePropertyType
from .crresult import CR_BUFFER_SMALL, CR_NO_SUCH_VALUE, CR_SUCCESS


class CMError(Exception):
    cr: int

    def __init__(self, cr: int) -> None:
        self.cr = cr


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
    __slots__ = ("guid",)
    guid: Guid

    def __init__(self, guid: Guid) -> None:
        self.guid = Guid.from_buffer_copy(guid)

    @staticmethod
    @abstractmethod
    def classenumflags() -> int: ...

    @staticmethod
    @abstractmethod
    def classpropflags() -> int: ...

    @classmethod
    def iter(cls) -> "Iterator[Self]":
        flags = cls.classenumflags()
        guid = Guid()
        for i in range(0xFFFFFFFF):
            cr = _CM_Enumerate_Classes(i, byref(guid), flags)
            if cr == CR_NO_SUCH_VALUE:
                return
            yield cls(guid)
        raise OverflowError

    @property
    def propkeycount(self) -> int:
        flags = self.classpropflags()

        c = c_uint32()
        cr = _CM_Get_Class_Property_Keys(self.guid, None, byref(c), flags)
        if cr == CR_SUCCESS or cr == CR_BUFFER_SMALL:
            return c.value
        else:
            raise CMError(cr)

    @property
    def propkeys(self) -> tuple[DevicePropertyKey, ...]:
        flags = self.classpropflags()

        c = c_uint32()
        cr = _CM_Get_Class_Property_Keys(self.guid, None, byref(c), flags)
        if cr == CR_SUCCESS:
            return ()
        elif cr != CR_BUFFER_SMALL:
            raise CMError(cr)

        keys = (DevicePropertyKey * c.value)()
        cr = _CM_Get_Class_Property_Keys(self.guid, keys, byref(c), flags)
        if cr != CR_SUCCESS:
            raise CMError(cr)
        return tuple(keys)

    def get_prop(self, key: DevicePropertyKey) -> DeviceProperty:
        flags = self.classpropflags()

        type = c_int32()
        bufsize = c_uint32()
        cr = _CM_Get_Class_PropertyW(self.guid, key, byref(type), None, byref(bufsize), flags)
        if cr != CR_BUFFER_SMALL:
            raise CMError(cr)

        buf = (c_byte * bufsize.value)()
        cr = _CM_Get_Class_PropertyW(self.guid, key, byref(type), buf, byref(bufsize), flags)
        if cr != CR_SUCCESS:
            raise CMError(cr)

        return DeviceProperty(key, DevicePropertyType(type.value), bytes(buf))

    @property
    def props(self) -> tuple[DeviceProperty, ...]:
        return tuple(self.get_prop(key) for key in self.propkeys)


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


_cfgmgr32 = WinDLL("cfgmgr32.dll")

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
