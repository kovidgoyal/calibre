from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''Read meta information from PDF files'''

import os, subprocess, shutil, re
from functools import partial

from calibre import prints
from calibre.constants import iswindows
from calibre.ptempfile import TemporaryDirectory
from calibre.ebooks.metadata import (
    MetaInformation, string_to_authors, check_isbn, check_doi)
from calibre.utils.ipc.simple_worker import fork_job, WorkerError

#_isbn_pat = re.compile(r'ISBN[: ]*([-0-9Xx]+)')

def get_tools():
    from calibre.ebooks.pdf.pdftohtml import PDFTOHTML
    base = os.path.dirname(PDFTOHTML)
    suffix = '.exe' if iswindows else ''
    pdfinfo = os.path.join(base, 'pdfinfo') + suffix
    pdftoppm = os.path.join(base, 'pdftoppm') + suffix
    return pdfinfo, pdftoppm

def read_info(outputdir, get_cover):
    ''' Read info dict and cover from a pdf file named src.pdf in outputdir.
    Note that this function changes the cwd to outputdir and is therefore not
    thread safe. Run it using fork_job. This is necessary as there is no safe
    way to pass unicode paths via command line arguments. This also ensures
    that if poppler crashes, no stale file handles are left for the original
    file, only for src.pdf.'''
    os.chdir(outputdir)
    pdfinfo, pdftoppm = get_tools()
    ans = {}

    try:
        raw = subprocess.check_output([pdfinfo, '-meta', '-enc', 'UTF-8', 'src.pdf'])
    except subprocess.CalledProcessError as e:
        prints('pdfinfo errored out with return code: %d'%e.returncode)
        return None
    # The XMP metadata could be in an encoding other than UTF-8, so split it
    # out before trying to decode raw
    parts = re.split(br'^Metadata:', raw, 1, flags=re.MULTILINE)
    if len(parts) > 1:
        raw, ans['xmp_metadata'] = parts
    try:
        raw = raw.decode('utf-8')
    except UnicodeDecodeError:
        prints('pdfinfo returned no UTF-8 data')
        return None

    for line in raw.splitlines():
        if u':' not in line:
            continue
        field, val = line.partition(u':')[::2]
        val = val.strip()
        if field and val:
            ans[field] = val.strip()

    if get_cover:
        try:
            subprocess.check_call([pdftoppm, '-singlefile', '-jpeg', '-cropbox',
                'src.pdf', 'cover'])
        except subprocess.CalledProcessError as e:
            prints('pdftoppm errored out with return code: %d'%e.returncode)

    return ans

def page_images(pdfpath, outputdir, first=1, last=1):
    pdftoppm = get_tools()[1]
    outputdir = os.path.abspath(outputdir)
    args = {}
    if iswindows:
        import win32process as w
        args['creationflags'] = w.HIGH_PRIORITY_CLASS | w.CREATE_NO_WINDOW
    try:
        subprocess.check_call([pdftoppm, '-cropbox', '-jpeg', '-f', unicode(first),
                               '-l', unicode(last), pdfpath,
                               os.path.join(outputdir, 'page-images')], **args)
    except subprocess.CalledProcessError as e:
        raise ValueError('Failed to render PDF, pdftoppm errorcode: %s'%e.returncode)

def get_metadata(stream, cover=True):
    with TemporaryDirectory('_pdf_metadata_read') as pdfpath:
        stream.seek(0)
        with open(os.path.join(pdfpath, 'src.pdf'), 'wb') as f:
            shutil.copyfileobj(stream, f)
        try:
            res = fork_job('calibre.ebooks.metadata.pdf', 'read_info',
                    (pdfpath, bool(cover)))
        except WorkerError as e:
            prints(e.orig_tb)
            raise RuntimeError('Failed to run pdfinfo')
        info = res['result']
        with open(res['stdout_stderr'], 'rb') as f:
            raw = f.read().strip()
            if raw:
                prints(raw)
        if not info:
            raise ValueError('Could not read info dict from PDF')
        covpath = os.path.join(pdfpath, 'cover.jpg')
        cdata = None
        if cover and os.path.exists(covpath):
            with open(covpath, 'rb') as f:
                cdata = f.read()

    title = info.get('Title', None)
    au = info.get('Author', None)
    if au is None:
        au = [_('Unknown')]
    else:
        au = string_to_authors(au)
    mi = MetaInformation(title, au)
    # if isbn is not None:
    #    mi.isbn = isbn

    creator = info.get('Creator', None)
    if creator:
        mi.book_producer = creator

    keywords = info.get('Keywords', None)
    mi.tags = []
    if keywords:
        mi.tags = [x.strip() for x in keywords.split(',')]
        isbn = [check_isbn(x) for x in mi.tags if check_isbn(x)]
        if isbn:
            mi.isbn = isbn = isbn[0]
        mi.tags = [x for x in mi.tags if check_isbn(x) != isbn]

    subject = info.get('Subject', None)
    if subject:
        mi.tags.insert(0, subject)

    if 'xmp_metadata' in info:
        from calibre.ebooks.metadata.xmp import consolidate_metadata
        mi = consolidate_metadata(mi, info)

    # Look for recognizable identifiers in the info dict, if they were not
    # found in the XMP metadata
    for scheme, check_func in {'doi':check_doi, 'isbn':check_isbn}.iteritems():
        if scheme not in mi.get_identifiers():
            for k, v in info.iteritems():
                if k != 'xmp_metadata':
                    val = check_func(v)
                    if val:
                        mi.set_identifier(scheme, val)
                        break

    if cdata:
        mi.cover_data = ('jpeg', cdata)
    return mi

get_quick_metadata = partial(get_metadata, cover=False)

from calibre.utils.podofo import set_metadata as podofo_set_metadata

def set_metadata(stream, mi):
    stream.seek(0)
    return podofo_set_metadata(stream, mi)


