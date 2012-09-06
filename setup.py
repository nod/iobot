#!/usr/bin/env python

from setuptools import setup, find_packages

VERSION = open('VERSION').read().lstrip('version: ').rstrip('\n')

setup(
    name = 'iobot',
    version = VERSION,
    description = 'tornado ioloop based irc bot',
    author = 'Jeremy Kelley',
    author_email = 'jeremy@33ad.org',
    url = 'https://github.com/nod/iobot',
    license = "http://www.apache.org/licenses/LICENSE-2.0",
    packages = find_packages(),
    package_dir={'mypkg': 'src/mypkg'},
    install_requires = ['tornado', 'nose', 'mock', 'requests']
    )

