#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, sys, subprocess
from distutils.msvc9compiler import find_vcvarsall, get_build_version

plat = 'amd64' if sys.maxsize > 2**32 else 'x86'

def remove_dups(variable):
    old_list = variable.split(os.pathsep)
    new_list = []
    for i in old_list:
        if i not in new_list:
            new_list.append(i)
    return os.pathsep.join(new_list)

def query_process(cmd):
    result = {}
    popen = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
    try:
        stdout, stderr = popen.communicate()
        if popen.wait() != 0:
            raise RuntimeError(stderr.decode("mbcs"))

        stdout = stdout.decode("mbcs")
        for line in stdout.splitlines():
            if '=' not in line:
                continue
            line = line.strip()
            key, value = line.split('=', 1)
            key = key.lower()
            if key == 'path':
                if value.endswith(os.pathsep):
                    value = value[:-1]
                value = remove_dups(value)
            result[key] = value

    finally:
        popen.stdout.close()
        popen.stderr.close()
    return result

def query_vcvarsall():
    vcvarsall = find_vcvarsall(get_build_version())
    return query_process('"%s" %s & set' % (vcvarsall, plat))

env = query_vcvarsall()
paths = env['path'].split(';')
lib = env['lib']
include = env['include']
libpath = env['libpath']

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

export LIBPATH="%s"

'''%(unix(paths), lib, include, libpath)

with open(os.path.expanduser('~/.vcvars'), 'wb') as f:
    f.write(raw.encode('utf-8'))

