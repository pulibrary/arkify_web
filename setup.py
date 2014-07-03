#!/usr/bin/env python

from os.path import dirname
from os.path import join
from os.path import realpath
from setuptools import setup
from shutil import copy
from sys import stdout

NAME='Arkify Web'
VERSION='0.0.2dev'
DESCRIPTION='Simple web form for for making ARKS @ PUL.'
AUTHOR='Jon Stroop'
AUTHOR_EMAIL='jpstroop@gmail.com'
URI=''
INSTALL_REQUIRES=['configobj', 'flask', 'requests']
DATA_FILES=[
  ('/etc', ['etc/arkform.conf']),
  ('/var/www', ['www/arkform.wsgi'])
]
PACKAGES=['arkform']

here = dirname(realpath(__file__))
copy(join(here, 'etc/arkform.conf.tmpl'), join(here, 'etc/arkform.conf'))

setup(name=NAME, 
  version=VERSION, 
  description=DESCRIPTION, 
  author=AUTHOR,
  author_email=AUTHOR_EMAIL, 
  url=URI, 
  install_requires=INSTALL_REQUIRES,
  packages=PACKAGES,
  data_files=DATA_FILES
)

stdout.write('*'*79+'\n')
stdout.write(NAME+'\n')
stdout.write('If installation was successful, you should now be able to configure the\n')
stdout.write('application in /etc/arkform.conf.\n')
stdout.write('*'*79+'\n')
