# powdeviceinfoパッケージ

PythonからWindowsのデバイス管理機能を使いやすくするパッケージです。デバイスプロパティ、コンフィグマネージャーを含みます。標準ライブラリとpowguidパッケージに依存します。

## powdeviceinfo.devprop

デバイスプロパティ、型、定数。

## powdeviceinfo.cfgmgr

**セットアップクラスのクラス名を取得**

```py
from pprint import pp

from powdeviceinfo.cfgmgr import CMSetupClass

pp(sorted(cls.classname_or_none or "" for cls in CMSetupClass.iter()))
```

**バッテリークラスデバイスの情報を取得**

```py
from powdeviceinfo.cfgmgr import CMDevice

for device in CMDevice.iter_deviceid_by_classname("battery", True):
    print((device.devinst, device.name_or_none, device.instanceid_or_none))
```
