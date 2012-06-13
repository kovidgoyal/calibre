#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, time, shutil

from calibre.constants import plugins, preferred_encoding
from calibre.ebooks.metadata import MetaInformation, string_to_authors, \
    authors_to_string
from calibre.utils.ipc.job import ParallelJob
from calibre.utils.ipc.server import Server
from calibre.ptempfile import PersistentTemporaryFile, TemporaryFile
from calibre import prints

podofo, podofo_err = plugins['podofo']

class Unavailable(Exception): pass

def get_metadata(stream, cpath=None):
    if not podofo:
        raise Unavailable(podofo_err)
    pt = PersistentTemporaryFile('_podofo.pdf')
    pt.write(stream.read())
    pt.close()
    server = Server(pool_size=1)
    job = ParallelJob('read_pdf_metadata', 'Read pdf metadata',
        lambda x,y:x,  args=[pt.name, cpath])
    server.add_job(job)
    while not job.is_finished:
        time.sleep(0.1)
        job.update()

    job.update()
    server.close()
    if job.result is None:
        raise ValueError('Failed to read metadata: ' + job.details)
    title, authors, creator, tags, ok = job.result
    if not ok:
        print 'Failed to extract cover:'
        print job.details
    if title == '_':
        title = getattr(stream, 'name', _('Unknown'))
        title = os.path.splitext(title)[0]

    mi = MetaInformation(title, authors)
    if creator:
        mi.book_producer = creator
    if tags:
        mi.tags = tags
    if os.path.exists(pt.name): os.remove(pt.name)
    if ok:
        mi.cover = cpath
    return mi

def get_metadata_quick(raw):
    p = podofo.PDFDoc()
    p.load(raw)
    title = p.title
    if not title:
        title = '_'
    author = p.author
    authors = string_to_authors(author) if author else  [_('Unknown')]
    creator = p.creator
    try:
        tags = [x.strip() for x in p.keywords.split(u',')]
        tags = [x for x in tags if x]
    except:
        tags = []

    mi = MetaInformation(title, authors)
    if creator:
        mi.book_producer = creator
    if tags:
        mi.tags = tags
    return mi

def get_metadata_(path, cpath=None):
    p = podofo.PDFDoc()
    p.open(path)
    title = p.title
    if not title:
        title = '_'
    author = p.author
    authors = string_to_authors(author) if author else  [_('Unknown')]
    creator = p.creator
    try:
        tags = [x.strip() for x in p.keywords.split(u',')]
        tags = [x for x in tags if x]
    except:
        tags = []
    ok = True
    try:
        if cpath is not None:
            pages = p.pages
            if pages < 1:
                raise ValueError('PDF has no pages')
            if True or pages == 1:
                shutil.copyfile(path, cpath)
            else:
                p.extract_first_page()
                p.save(cpath)
    except:
        import traceback
        traceback.print_exc()
        ok = False

    return (title, authors, creator, tags, ok)

def prep(val):
    if not val:
        return u''
    if not isinstance(val, unicode):
        val = val.decode(preferred_encoding, 'replace')
    return val.strip()

def set_metadata(stream, mi):
    if not podofo:
        raise Unavailable(podofo_err)
    with TemporaryFile('_podofo_read.pdf') as inputf, \
            TemporaryFile('_podofo_write.pdf') as outputf:
        server = Server(pool_size=1)
        with open(inputf, 'wb') as f:
            shutil.copyfileobj(stream, f)
        job = ParallelJob('write_pdf_metadata', 'Write pdf metadata',
            lambda x,y:x,  args=[inputf, outputf, mi.title, mi.authors,
                mi.book_producer, mi.tags])
        server.add_job(job)
        while not job.is_finished:
            time.sleep(0.1)
            job.update()

        job.update()
        server.close()
        if job.failed:
            prints(job.details)
        elif job.result:
            with open(outputf, 'rb') as f:
                f.seek(0, 2)
                if f.tell() > 100:
                    f.seek(0)
                    stream.seek(0)
                    stream.truncate()
                    shutil.copyfileobj(f, stream)
                    stream.flush()
    stream.seek(0)


def set_metadata_(path, opath, title, authors, bkp, tags):
    p = podofo.PDFDoc()
    p.open(path)
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
        p.save(opath)
        return True
    return False

def delete_all_but(path, pages):
    ''' Delete all the pages in the pdf except for the specified ones. Negative
    numbers are counted from the end of the PDF.'''
    with TemporaryFile('_podofo_in.pdf') as of:
        shutil.copyfile(path, of)

        p = podofo.PDFDoc()
        p.open(of)
        total = p.page_count()
        pages = { total + x if x < 0 else x for x in pages }
        for page in xrange(total-1, -1, -1):
            if page not in pages:
                p.delete_page(page)
        os.remove(path)
        p.save(path)

if __name__ == '__main__':
    f = '/tmp/t.pdf'
    delete_all_but(f, [0, 1, -2, -1])

