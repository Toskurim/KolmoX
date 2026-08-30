from setuptools import setup, Extension
from setuptools.command.build_ext import build_ext

class OptionalBuildExt(build_ext):
    def build_extension(self, ext):
        try:
            super().build_extension(ext)
        except Exception as e:
            print(f"Warning: Could not build C extension {ext.name}. Using pure-Python/NumPy fallback.")

fast_ext = Extension(
    "kolmox.core.fast_transforms",
    sources=["src/kolmox/core/fast_transforms.c"],
    optional=True,
)

setup(
    ext_modules=[fast_ext],
    cmdclass={"build_ext": OptionalBuildExt},
)
