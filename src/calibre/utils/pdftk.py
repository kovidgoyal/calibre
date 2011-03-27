#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


import sys, subprocess, os, errno
from functools import partial
from contextlib import nested

from calibre.ptempfile import TemporaryFile
from calibre.constants import iswindows

PDFTK = 'pdftk'
popen = subprocess.Popen
#if isosx and hasattr(sys, 'frameworks_dir'):
#    PDFTK = os.path.join(getattr(sys, 'frameworks_dir'), 'pdftk')
if iswindows and hasattr(sys, 'frozen'):
    PDFTK = os.path.join(os.path.dirname(sys.executable), 'pdftk.exe')
    popen = partial(subprocess.Popen, creationflags=0x08) # CREATE_NO_WINDOW=0x08 so that no ugly console is popped up

class PdftkError(Exception): pass

def mi_to_info(mi):
    ans = []
    if mi.title:
        ans.extend(('InfoKey: Title', 'InfoValue: '+mi.title))
    if mi.authors:
        from calibre.ebooks.metadata import authors_to_string
        ans.extend(('InfoKey: Author', 'InfoValue: ' +
            authors_to_string(mi.authors)))
    return u'\n'.join(ans)

def set_metadata(stream, mi):
    raw = mi_to_info(mi)
    if not raw: return
    raw = raw.encode('utf-8')
    with nested(TemporaryFile('.pdf'), TemporaryFile('.pdf'),
            TemporaryFile('.info')) as (input, output, meta):
        oi = getattr(stream, 'name', None)
        if not oi or not os.access(oi, os.R_OK):
            stream.seek(0)
            with open(input, 'wb') as f: f.write(stream.read())
        else:
            input = oi
        with open(meta, 'wb') as f: f.write(raw)
        if os.path.exists(output):
            os.remove(output)
        cmd = (PDFTK, input, 'update_info', meta, 'output', output)
        p = popen(cmd)

        while True:
            try:
                p.wait()
                break
            except OSError as e:
                if e.errno == errno.EINTR:
                    continue
                else:
                    raise

        if os.stat(output).st_size < 2048:
            raise PdftkError('Output file too small')

        with open(output, 'rb') as f: raw = f.read()
        if raw:
            stream.seek(0)
            stream.truncate()
            stream.write(raw)
            stream.flush()

if __name__ == '__main__':
    args = sys.argv
    from calibre.ebooks.metadata import MetaInformation
    mi = MetaInformation(args[2], [args[3]])
    x = open(args[1], 'r+b')
    set_metadata(x, mi)
