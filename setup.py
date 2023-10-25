#!/usr/bin/python

"""Installation routines."""

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

from setuptools import setup, find_packages

def do_setup():
    """Execute the setup thanks to setuptools."""
    setup(name="log-patch",
          version="0.3.0",
          author="Keith Suderman",
          author_email="keithsuderman@gmail.com",
          url="",
          download_url="",
          description="Patch log statements that use greedy string interpolation.",
          entry_points={
              "console_scripts": ["logfix=logfix.main:main","loglint=logfix.linter:main"]
          },
          keywords="log logging lazy interpolation python",
          license="MIT",
          classifiers=[
              "Development Status :: 3 - Alpha",
              "Natural Language :: English",
              "Operating System :: POSIX :: Linux",
              "Programming Language :: Python :: 3",
              "License :: OSI Approved :: MIT"
          ],
          packages=find_packages()
          )


if __name__ == "__main__":
    do_setup()
