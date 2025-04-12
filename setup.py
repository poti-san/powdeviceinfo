from setuptools import find_packages, setup

setup(
    name="powdeviceinfo",
    version="0.0.1",
    install_requires=("powguid",),
    packages=find_packages(where="src"),
    package_dir={"": "src"},
)
