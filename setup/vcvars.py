#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os
from distutils.msvc9compiler import MSVCCompiler

c = MSVCCompiler()
orig_path = os.environ['path']
c.initialize()
paths = c._MSVCCompiler__paths
lib = os.environ['lib'].split(';')
include = os.environ['include'].split(';')

def unix(paths):
    up = []
    for p in paths:
        prefix, p = p.replace(os.sep, '/').partition('/')[0::2]
        up.append('/cygdrive/%s/%s'%(prefix[0].lower(), p))
    return ':'.join(up)

raw = '''\
#!/bin/sh

export PATH="%s:$PATH"
export LIB="%s"
export INCLUDE="%s"
'''%(unix(paths), ';'.join(lib), ';'.join(include))

with open(os.path.expanduser('~/.vcvars'), 'wb') as f:
    f.write(raw.encode('utf-8'))

