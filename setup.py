from setuptools import setup, find_packages

setup(
    name="kolmox",
    version="0.1.0",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=[
        "zstandard>=0.22.0",
        "numpy>=1.26.0",
        "rich>=13.7.0",
        "click>=8.1.0",
        "requests>=2.31.0",
    ],
    entry_points={
        "console_scripts": [
            "kolmox = kolmox.cli.main:cli",
        ],
    },
)