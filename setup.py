#!/usr/bin/env python3

from setuptools import setup, find_packages
from urllib.parse import urlparse

with open('requirements.txt', 'r') as f:
    install_requires = []
    dependency_links = []
    requirements = [ line.strip() for line in f ]
    for requirement in requirements:
        name = urlparse(requirement)
        if name.scheme and name.netloc:
            dependency_links.append(requirement)
        else:
            install_requires.append(requirement)


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
      install_requires=install_requires,
      dependency_links=dependency_links,
      entry_points="""\
      [console_scripts]
      kochira = kochira:main
      """
      )
