import os
import shutil
import sys

# import pip
from Cython.Build import cythonize
from setuptools import Distribution, Extension
from setuptools.command import build_ext


def build() -> None:
    compile_args = []

    if sys.platform == "linux":
        compile_args += ["-Wno-pointer-sign", "-Wno-unused-variable"]

    extensions = [
        Extension(
            "pyModeS.c_common",
            ["pyModeS/c_common.pyx"],
            extra_compile_args=compile_args,
        ),
        Extension(
            "pyModeS.decoder.flarm.decode",
            [
                "pyModeS/decoder/flarm/decode.pyx",
                "pyModeS/decoder/flarm/core.c",
            ],
            extra_compile_args=compile_args,
            include_dirs=["pyModeS/decoder/flarm"],
        ),
        # Extension(
        #     "pyModeS.extra.demod2400.core",
        #     [
        #         "pyModeS/extra/demod2400/core.pyx",
        #         "pyModeS/extra/demod2400/demod2400.c",
        #     ],
        #     extra_compile_args=compile_args,
        #     include_dirs=["pyModeS/extra/demod2400"],
        #     libraries=["m"],
        # ),
    ]

    ext_modules = cythonize(
        extensions,
        compiler_directives={"binding": True, "language_level": 3},
    )

    distribution = Distribution({"name": "extended", "ext_modules": ext_modules})
    distribution.package_dir = "extended"  # type: ignore

    cmd = build_ext.build_ext(distribution)
    cmd.verbose = True  # type: ignore
    cmd.ensure_finalized()  # type: ignore
    cmd.run()

    # Copy built extensions back to the project
    for output in cmd.get_output_mapping():
        relative_extension = os.path.relpath(output, cmd.build_lib)
        shutil.copyfile(output, relative_extension)
        mode = os.stat(relative_extension).st_mode
        mode |= (mode & 0o444) >> 2
        os.chmod(relative_extension, mode)


if __name__ == "__main__":
    build()
