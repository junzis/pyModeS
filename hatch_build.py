import sys
from pathlib import Path

from Cython.Build import cythonize
from hatchling.builders.hooks.plugin.interface import BuildHookInterface
from setuptools import Distribution, Extension
from setuptools.command import build_ext


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        """Initialize the build hook."""
        compile_args = []

        if sys.platform == "linux":
            compile_args += ["-Wno-pointer-sign", "-Wno-unused-variable"]

        extensions = [
            Extension(
                "pyModeS.c_common",
                sources=["src/pyModeS/c_common.pyx"],
                include_dirs=["src"],
                extra_compile_args=compile_args,
            ),
            Extension(
                "pyModeS.decoder.flarm.decode",
                [
                    "src/pyModeS/decoder/flarm/decode.pyx",
                    "src/pyModeS/decoder/flarm/core.c",
                ],
                extra_compile_args=compile_args,
                include_dirs=["src/pyModeS/decoder/flarm"],
            ),
            # Extension(
            #     "pyModeS.extra.demod2400.core",
            #     [
            #         "src/pyModeS/extra/demod2400/core.pyx",
            #         "src/pyModeS/extra/demod2400/demod2400.c",
            #     ],
            #     extra_compile_args=compile_args,
            #     include_dirs=["src/pyModeS/extra/demod2400"],
            #     libraries=["m"],
            # ),
        ]

        ext_modules = cythonize(
            extensions,
            compiler_directives={"binding": True, "language_level": 3},
        )

        # Create a dummy distribution object
        dist = Distribution(dict(name="pyModeS", ext_modules=ext_modules))
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
            ).as_posix(): cmd.get_ext_filename("pyModeS.c_common"),
            (
                buildpath / cmd.get_ext_filename("pyModeS.decoder.flarm.decode")
            ).as_posix(): cmd.get_ext_filename("pyModeS.decoder.flarm.decode"),
        }

        build_data["pure_python"] = False
        build_data["infer_tag"] = True
        build_data["force_include"].update(force_include)

        return super().initialize(version, build_data)

    def finalize(self, version, build_data, artifact_path):
        """Hook called after the build."""
        return super().finalize(version, build_data, artifact_path)
