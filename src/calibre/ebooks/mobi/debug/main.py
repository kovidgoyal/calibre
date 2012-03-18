#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys, os, shutil

from calibre.ebooks.mobi.debug.headers import MOBIFile
from calibre.ebooks.mobi.debug.mobi6 import inspect_mobi as inspect_mobi6
from calibre.ebooks.mobi.debug.mobi8 import inspect_mobi as inspect_mobi8

def inspect_mobi(path_or_stream, ddir=None): # {{{
    stream = (path_or_stream if hasattr(path_or_stream, 'read') else
            open(path_or_stream, 'rb'))
    f = MOBIFile(stream)
    if ddir is None:
        ddir = 'decompiled_' + os.path.splitext(os.path.basename(stream.name))[0]
    try:
        shutil.rmtree(ddir)
    except:
        pass
    os.makedirs(ddir)
    if f.kf8_type is None:
        inspect_mobi6(f, ddir)
    elif f.kf8_type == 'joint':
        p6 = os.path.join(ddir, 'mobi6')
        os.mkdir(p6)
        inspect_mobi6(f, p6)
        p8 = os.path.join(ddir, 'mobi8')
        os.mkdir(p8)
        inspect_mobi8(f, p8)
    else:
        inspect_mobi8(f, ddir)

    print ('Debug data saved to:', ddir)

# }}}

def main():
    inspect_mobi(sys.argv[1])

if __name__ == '__main__':
    main()

