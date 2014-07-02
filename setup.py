#!/usr/bin/env python

from distutils.core import setup

NAME='Arkify Web'
VERSION='0.0.1'
DESCRIPTION='Simple web for for making ARKS @ PUL.'
AUTHOR='Jon Stroop'
AUTHOR_EMAIL='jpstroop@gmail.com'
PACKAGES=['Flask-Assets', 'Flask']
URI=''
PACKAGE_DIRS={'': 'lib'}

setup(name=NAME, version=VERSION, description=DESCRIPTION, author=AUTHOR,
      author_email=AUTHOR_EMAIL, url=URI, package_dir=PACKAGE_DIRS,
      packages=PACKAGES)
