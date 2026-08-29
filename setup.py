from setuptools import setup, find_packages, Extension

fast_ops = Extension(
    "kolmox.c_ext.fast_ops",
    sources=["src/kolmox/c_ext/fast_ops.c"],
)

setup(
    name="kolmox",
    version="0.1.0",
    package_dir={"": "src"},
    packages=find_packages("where="src"),
    ext_modules=[fast_ops],
    entry_points={
        "console_scripts": [
            "kolmox=kolmox.cli.main:cli",
        ],
    },
)
