from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface
from setuptools import Distribution, Extension
from setuptools.command import build_ext


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        """Initialize the build hook."""
        extensions = [
            Extension(
                "pyModeS.c_common",
                sources=["src/pyModeS/c_common.pyx"],
                include_dirs=["src"],
            )
        ]

        # Create a dummy distribution object
        dist = Distribution(dict(name="pyModeS", ext_modules=extensions))
        dist.package_dir = "pyModeS"

        # Create and run the build_ext command
        cmd = build_ext.build_ext(dist)
        cmd.verbose = True
        cmd.ensure_finalized()
        cmd.run()

        buildpath = Path(cmd.build_lib)

        # Provide locations of compiled modules
        force_include = {
            (
                buildpath / cmd.get_ext_filename("pyModeS.c_common")
            ).as_posix(): cmd.get_ext_filename("pyModeS.c_common")
        }

        build_data["pure_python"] = False
        build_data["infer_tag"] = True
        build_data["force_include"].update(force_include)

        return super().initialize(version, build_data)

    def finalize(self, version, build_data, artifact_path):
        """Hook called after the build."""
        return super().finalize(version, build_data, artifact_path)
