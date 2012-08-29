#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, shutil

from calibre.constants import plugins, preferred_encoding
from calibre.ebooks.metadata import authors_to_string
from calibre.ptempfile import TemporaryDirectory
from calibre.utils.ipc.simple_worker import fork_job, WorkerError

def get_podofo():
    podofo, podofo_err = plugins['podofo']
    if podofo is None:
        raise RuntimeError('Failed to load podofo: %s'%podofo_err)
    return podofo

def prep(val):
    if not val:
        return u''
    if not isinstance(val, unicode):
        val = val.decode(preferred_encoding, 'replace')
    return val.strip()

def set_metadata(stream, mi):
    with TemporaryDirectory(u'_podofo_set_metadata') as tdir:
        with open(os.path.join(tdir, u'input.pdf'), 'wb') as f:
            shutil.copyfileobj(stream, f)
        try:
            touched = fork_job('calibre.utils.podofo', 'set_metadata_', (tdir,
                mi.title, mi.authors, mi.book_producer, mi.tags))
        except WorkerError as e:
            raise Exception('Failed to set PDF metadata: %s'%e.orig_tb)
        if touched:
            with open(os.path.join(tdir, u'output.pdf'), 'rb') as f:
                f.seek(0, 2)
                if f.tell() > 100:
                    f.seek(0)
                    stream.seek(0)
                    stream.truncate()
                    shutil.copyfileobj(f, stream)
                    stream.flush()
    stream.seek(0)

def set_metadata_(tdir, title, authors, bkp, tags):
    podofo = get_podofo()
    os.chdir(tdir)
    p = podofo.PDFDoc()
    p.open(u'input.pdf')
    title = prep(title)
    touched = False
    if title and title != p.title:
        p.title = title
        touched = True

    author = prep(authors_to_string(authors))
    if author and author != p.author:
        p.author = author
        touched = True

    bkp = prep(bkp)
    if bkp and bkp != p.creator:
        p.creator = bkp
        touched = True

    try:
        tags = prep(u', '.join([x.strip() for x in tags if x.strip()]))
        if tags != p.keywords:
            p.keywords = tags
            touched = True
    except:
        pass

    if touched:
        p.save(u'output.pdf')

    return touched

def delete_all_but(path, pages):
    ''' Delete all the pages in the pdf except for the specified ones. Negative
    numbers are counted from the end of the PDF. '''
    podofo = get_podofo()
    p = podofo.PDFDoc()
    with open(path, 'rb') as f:
        raw = f.read()
    p.load(raw)
    total = p.page_count()
    pages = { total + x if x < 0 else x for x in pages }
    for page in xrange(total-1, -1, -1):
        if page not in pages:
            p.delete_page(page)

    raw = p.write()
    with open(path, 'wb') as f:
        f.write(raw)

def test_outline(src):
    podofo = get_podofo()
    p = podofo.PDFDoc()
    with open(src, 'rb') as f:
        raw = f.read()
    p.load(raw)
    total = p.page_count()
    root = p.create_outline(u'Table of Contents')
    for i in xrange(0, total):
        root.create(u'Page %d'%i, i, True)
    raw = p.write()
    out = '/tmp/outlined.pdf'
    with open(out, 'wb') as f:
        f.write(raw)
    print 'Outlined PDF:', out

if __name__ == '__main__':
    import sys
    test_outline(sys.argv[-1])

