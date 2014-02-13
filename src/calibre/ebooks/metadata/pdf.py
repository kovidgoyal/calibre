__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''Read meta information from PDF files'''

import re, os, subprocess, shutil
from functools import partial

from calibre import prints
from calibre.constants import iswindows
from calibre.ptempfile import TemporaryDirectory
from calibre.ebooks.metadata import MetaInformation, string_to_authors, check_isbn
from calibre.ebooks.pdf.xmp_parser import xmp_to_dict
from calibre.utils.ipc.simple_worker import fork_job, WorkerError

#_isbn_pat = re.compile(r'ISBN[: ]*([-0-9Xx]+)')
_doi_search = re.compile(u'10\.\d{4}/\S+')
_PMCID_search = re.compile(u'PMC\d+')
_arXiv_new_search = re.compile(u'\d{4}\.\d{4}v?\d*')
arXiv_fields = ['astro-ph', 'cond-mat', 'gr-qc', 'hep-ex', 'hep-lat', 'hep-ph',
                'hep-th', 'math-ph', 'nlin', 'nucl-ex', 'nucl-th', 'physics',
                'quant-ph ', 'math', 'CoRR', 'q-bio', 'q-fin', 'stat']
_arXiv_old_search = re.compile(u'(%s)/[\dv]+'%(u'|'.join(arXiv_fields)))

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

    try:
        raw = subprocess.check_output([pdfinfo, '-enc', 'UTF-8', '-meta', 'src.pdf'])
    except subprocess.CalledProcessError as e:
        prints('pdfinfo errored out with return code: %d'%e.returncode)
        return None
    try:
        raw = raw.decode('utf-8')
    except UnicodeDecodeError:
        prints('pdfinfo returned no UTF-8 data')
        return None

    info, metadata = raw.split(u'Metadata:',1)
    lines = [line.partition(u':')[::2] for line in info.splitlines() \
                if u':' in line]
    ans = {field: val.strip() for field, val in lines \
                if (field and val.strip())}
    ans[u'Metadata'] = metadata.strip()

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

def get_meta_ids(info):
    ''' Try to extract DOI (or other meta ids) from technical literature pdfs.
    Look into metadata object and check different known scheme.
    If multiple, weighted decision in the end'''
    # TODO: Check the first page of the pdf

    ids = {}
    DOI, arXiv, PMCID, dc_id = (None,None,None,None)

    metadata = info.get('Metadata', None)
    if metadata:
        meta_dict = xmp_to_dict(metadata)

        # DOI
        if 'prism' in meta_dict and 'doi' in meta_dict['prism']:
            DOI = meta_dict['prism']['doi']
        elif 'pdfx' in meta_dict and 'doi' in meta_dict['pdfx']:
            DOI = meta_dict['pdfx']['doi']
        elif 'dc' in meta_dict and 'identifier' in meta_dict['dc']:
            dc_id = meta_dict['dc']['identifier']

    info.pop('Metadata', None)
    if dc_id:
        arXiv = dc_id
        PMCID = dc_id
        if not DOI:
            DOI = dc_id

    # Check DOI
    if DOI:
        find_doi = _doi_search.search(DOI)
        if find_doi:
            ids['doi'] = find_doi.group()
        else:
            DOI = None
    # Check arXiv
    if arXiv:
        find_arXiv = _arXiv_new_search.search(arXiv)
        if not find_arXiv:
            find_arXiv = _arXiv_old_search.search(arXiv)
        if find_arXiv:
            ids['arxiv'] = find_arXiv.group()
        else:
            arXiv = None
    # Check PMCID
    if PMCID:
        find_PMCID = _PMCID_search.search(PMCID)
        if find_PMCID:
            ids['pmcid'] = find_PMCID.group()
        else:
            PMCID = None

    # Check usual infos for DOI, ArXIv
    for v in info.itervalues():
        if not DOI:
            find_doi = _doi_search.search(v)
            if find_doi:
                ids['doi'] = find_doi.group()
        if not PMCID:
            find_PMCID = _PMCID_search.search(v)
            if find_PMCID:
                ids['pmcid'] = find_PMCID.group()
        if not arXiv:
            find_arXiv = _arXiv_new_search.search(v)
            if not find_arXiv:
                find_arXiv = _arXiv_old_search.search(v)
            if find_arXiv:
                ids['arxiv'] = find_arXiv.group()

    return ids

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

    meta_ids = get_meta_ids(info)
    if meta_ids:
        for meta, id in meta_ids.iteritems():
            mi.set_identifier(meta,id)

    if cdata:
        mi.cover_data = ('jpeg', cdata)

    return mi

get_quick_metadata = partial(get_metadata, cover=False)

from calibre.utils.podofo import set_metadata as podofo_set_metadata

def set_metadata(stream, mi):
    stream.seek(0)
    return podofo_set_metadata(stream, mi)