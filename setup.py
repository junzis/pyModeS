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
    install_requires=["numpy", "pyzmq"],
    extras_require={"fast": ["Cython"]},
    package_data={"pyModeS": ["*.pyx", "*.pxd", "py.typed"]},
    scripts=["pyModeS/streamer/modeslive"],
)

try:
    from setuptools.extension import Extension
    from Cython.Build import cythonize

    extensions = [Extension("pyModeS.c_common", ["pyModeS/c_common.pyx"])]

    setup(**dict(details, ext_modules=cythonize(extensions)))

except ImportError:
    setup(**details)
