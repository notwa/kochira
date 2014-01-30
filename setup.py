#!/usr/bin/env python3

from setuptools import setup, find_packages

setup(name="kochira",
      version="0.0",
      description="kochira",
      author="",
      author_email="",
      url="",
      packages=find_packages(),
      include_package_data=True,
      zip_safe=False,
      test_suite="kochira",
      install_requires=[],
      entry_points="""\
      [console_scripts]
      kochira = kochira:main
      """
      )
