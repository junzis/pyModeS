"""A setuptools based setup module.

See:
https://packaging.python.org/en/latest/distributing.html
https://github.com/pypa/sampleproject

Steps for deploying a new version:
1. Increase the version number
2. remove the old deployment under [dist] and [build] folder
3. run: python setup.py sdist
4. twine upload dist/*
"""

import sys

# Always prefer setuptools over distutils
from setuptools import setup, find_packages

# To use a consistent encoding
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, "README.rst"), encoding="utf-8") as f:
    long_description = f.read()


details = dict(
    name="pyModeS",
    version="2.11",
    description="Python Mode-S and ADS-B Decoder",
    long_description=long_description,
    url="https://github.com/junzis/pyModeS",
    author="Junzi Sun",
    author_email="j.sun-1@tudelft.nl",
    license="GNU GPL v3",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Programming Language :: Python :: 3",
    ],
    keywords="Mode-S ADS-B EHS ELS Comm-B",
    packages=find_packages(exclude=["contrib", "docs", "tests"]),
    # typing_extensions are no longer necessary after Python 3.8 (TypedDict)
    install_requires=["numpy", "pyzmq", "typing_extensions"],
    extras_require={"fast": ["Cython"]},
    package_data={
        "pyModeS": ["*.pyx", "*.pxd", "py.typed"],
        "pyModeS.decoder.flarm": ["*.pyx", "*.pxd", "*.pyi"],
    },
    scripts=["pyModeS/streamer/modeslive"],
)

try:
    from distutils.core import Extension
    from Cython.Build import cythonize

    compile_args = []
    include_dirs = ["pyModeS/decoder/flarm"]

    if sys.platform == "linux":
        compile_args += [
            "-march=native",
            "-O3",
            "-msse",
            "-msse2",
            "-mfma",
            "-mfpmath=sse",
            "-Wno-pointer-sign",
        ]

    extensions = [
        Extension("pyModeS.c_common", ["pyModeS/c_common.pyx"]),
        Extension(
            "pyModeS.decoder.flarm.decode",
            [
                "pyModeS/decoder/flarm/decode.pyx",
                "pyModeS/decoder/flarm/core.c",
            ],
            extra_compile_args=compile_args,
            include_dirs=include_dirs,
        ),
    ]

    setup(
        **dict(
            details,
            ext_modules=cythonize(
                extensions,
                include_path=include_dirs,
                compiler_directives={"binding": True, "language_level": 3},
            ),
        )
    )

except ImportError:
    setup(**details)
