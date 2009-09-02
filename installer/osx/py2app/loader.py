#!/usr/bin/env python

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


import os, sys, cPickle

ENV = {}##ENV##
MODULE = ''##MODULE##

path = os.path.abspath(os.path.realpath(__file__))
dirpath = os.path.dirname(path)
name = os.path.basename(path)
base_dir = os.path.dirname(os.path.dirname(dirpath))
resources_dir = os.path.join(base_dir, 'Resources')
frameworks_dir = os.path.join(base_dir, 'Frameworks')
exe_dir = os.path.join(base_dir, 'MacOS')
base_name = os.path.splitext(name)[0]
python = os.path.join(base_dir, 'MacOS', 'Python')

for key, val in ENV.items():
    if val.startswith('@exec'):
        ENV[key] = os.path.normpath(val.replace('@executable_path', exe_dir))
ENV['CALIBRE_LAUNCH_MODULE'] = MODULE
ENV['CALIBRE_LAUNCH_ARGV'] = cPickle.dumps(sys.argv[1:], -1)
ENV['RESOURCEPATH'] = resources_dir
os.environ.update(ENV)
launcher = os.path.join(resources_dir, 'launcher.py')
args = ['-OO', launcher]
os.execv(python, args)

