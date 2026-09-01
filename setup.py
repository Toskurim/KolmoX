from setuptools import setup, Extension, find_packages
from setuptools.command.build_ext import build_ext
import os

class OptionalBuildExt(build_ext):
    def build_extension(self, ext):
        try:
            super().build_extension(ext)
        except Exception:
            print(f"Warning: Could not build C extension {ext.name}. Using pure-Python/NumPy fallback.")

long_description = ""
if os.path.exists("README.md"):
    with open("README.md", "r", encoding="utf-8") as f:
        long_description = f.read()

fast_ext = Extension(
    "kolmox.core.fast_transforms",
    sources=["src/kolmox/core/fast_transforms.c"],
    optional=True,
)

setup(
    name="kolmox",
    version="1.1.2",
    author="Toskurim",
    author_email="toskurim@gmail.com",
    description="Next-generation high-throughput domain-aware lossless data compression framework.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Toskurim/KolmoX",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    ext_modules=[fast_ext],
    cmdclass={"build_ext": OptionalBuildExt},
    entry_points={
        "console_scripts": [
            "kolmox=kolmox.cli.main:main",
        ],
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: GNU Affero General Public License v3 (AGPLv3)",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: System :: Archiving :: Compression",
    ],
    python_requires=">=3.10",
)
