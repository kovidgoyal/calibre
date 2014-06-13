#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

# The ICU build system does not put correct install names in the dylibs it
# generates. This script will fix that.

import os, glob, subprocess, re

SW = os.environ['SW']
cc = subprocess.check_call

icu_libs = {os.path.abspath(os.path.realpath(x)) for x in glob.glob(os.path.join(SW, 'lib', 'libicu*.dylib'))}

def get_install_name(lib):
    return subprocess.check_output(['otool', '-D', lib]).decode('utf-8').splitlines()[-1]

def get_dependencies(lib):
    return [x.strip().partition(' ')[0] for x in
            subprocess.check_output(['otool', '-L', lib]).decode('utf-8').splitlines()[2:]]

for lib in icu_libs:
    install_name = os.path.basename(lib)
    print ('Fixing install names in', install_name)
    m = re.match(r'libicu[a-z0-9]+\.\d+', install_name)
    install_name = m.group() + '.dylib'  # We only want the major version in the install name
    new_install_name = os.path.join(os.path.dirname(lib), install_name)
    cc(['install_name_tool', '-id', new_install_name, lib])
    for dep in get_dependencies(lib):
        name = os.path.basename(dep)
        if name.startswith('libicu'):
            ndep = os.path.join(SW, 'lib', name)
            if ndep != dep:
                cc(['install_name_tool', '-change', dep, ndep, lib])


