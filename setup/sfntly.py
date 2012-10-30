#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import shlex, os
from glob import glob

from setup import iswindows

class Group(object):

    def __init__(self, name, base, build_base, cflags):
        self.name = name
        self.cflags = cflags
        self.headers = frozenset(glob(os.path.join(base, '*.h')))
        self.src_files = glob(os.path.join(base, '*.cc'))
        self.bdir = os.path.abspath(os.path.join(build_base, name))
        if not os.path.exists(self.bdir):
            os.makedirs(self.bdir)
        self.objects = [os.path.join(self.bdir,
            os.path.basename(x).rpartition('.')[0] + ('.obj' if iswindows else
                '.o')) for x in self.src_files]

    def __call__(self, compiler, linker, builder, all_headers):
        for src, obj in zip(self.src_files, self.objects):
            if builder.newer(obj, [src] + list(all_headers)):
                sinc = ['/Tp'+src] if iswindows else ['-c', src]
                oinc = ['/Fo'+obj] if iswindows else ['-o', obj]
                cmd = [compiler] + self.cflags + sinc + oinc
                builder.info(' '.join(cmd))
                builder.check_call(cmd)

class SfntlyBuilderMixin(object):

    def __init__(self):
        self.sfntly_cflags = [
                '-DSFNTLY_NO_EXCEPTION',
                '-DSFNTLY_EXPERIMENTAL',
        ]
        if iswindows:
            self.sfntly_cflags += [
                    '-D_UNICODE', '-DUNICODE',
            ] + shlex.split('/W4 /WX /Gm- /Gy /GR-')
            self.cflags += ['-DWIN32']
        else:
            # Possibly add -fno-inline (slower, but more robust)
            self.sfntly_cflags += [
                    '-Werror',
                    '-fno-exceptions',
                    ]
        if len(self.libraries) > 1:
            self.libraries = ['icuuc']
        if not iswindows:
            self.libraries += ['pthread']

    def __call__(self, obj_dir, compiler, linker, builder, cflags, ldflags):
        self.sfntly_build_dir = os.path.join(obj_dir, 'sfntly')
        if '/Ox' in cflags:
            cflags.remove('/Ox')
        if '-O3' in cflags:
            cflags.remove('-O3')
        if '/W3' in cflags:
            cflags.remove('/W3')
        if '-ggdb' not in cflags:
            cflags.insert(0, '/O2' if iswindows else '-O2')

        groups = []
        all_headers = set()
        all_objects = []
        src_dir = self.absolutize([os.path.join('sfntly', 'src')])[0]
        inc_dirs = [src_dir]
        self.inc_dirs += inc_dirs
        inc_flags = builder.inc_dirs_to_cflags(self.inc_dirs)
        for loc in ('', 'port', 'data', 'math', 'table', 'table/bitmap',
                'table/core', 'table/truetype'):
            path = os.path.join(src_dir, 'sfntly', *loc.split('/'))
            gr = Group(loc, path, self.sfntly_build_dir, cflags+
                    inc_flags+self.sfntly_cflags+self.cflags)
            groups.append(gr)
            all_headers |= gr.headers
            all_objects.extend(gr.objects)

        for group in groups:
            group(compiler, linker, builder, all_headers)

        self.extra_objs = all_objects


