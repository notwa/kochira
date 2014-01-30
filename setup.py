#!/usr/bin/env python3

from setuptools import setup, find_packages

with open('requirements.txt', 'r') as f:
    requirements = [ line.strip() for line in f ]

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
      install_requires=requirements,
      entry_points="""\
      [console_scripts]
      kochira = kochira:main
      """
      )
