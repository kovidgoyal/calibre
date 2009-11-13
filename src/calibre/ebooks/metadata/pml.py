'''Read meta information from TXT files'''

from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'

import os
import glob
import re

from calibre.ebooks.metadata import MetaInformation
from calibre.ptempfile import TemporaryDirectory
from calibre.utils.zipfile import ZipFile

def get_metadata(stream, extract_cover=True):
    """ Return metadata as a L{MetaInfo} object """
    mi = MetaInformation(_('Unknown'), [_('Unknown')])
    stream.seek(0)

    pml = ''
    if stream.name.endswith('.pmlz'):
        with TemporaryDirectory('_unpmlz') as tdir:
            zf = ZipFile(stream)
            zf.extractall(tdir)

            pmls = glob.glob(os.path.join(tdir, '*.pml'))
            for p in pmls:
                with open(p, 'r+b') as p_stream:
                    pml += p_stream.read()
    else:
        pml = stream.read()

    for comment in re.findall(r'(?mus)\\v.*?\\v', pml):
        m = re.search(r'TITLE="(.*?)"', comment)
        if m:
            mi.title = m.group(1).strip().decode('cp1252', 'replace')
        m = re.search(r'AUTHOR="(.*?)"', comment)
        if m:
            if mi.authors == [_('Unknown')]:
                mi.authors = []
            mi.authors.append(m.group(1).strip().decode('cp1252', 'replace'))
        m = re.search(r'PUBLISHER="(.*?)"', comment)
        if m:
            mi.publisher = m.group(1).strip().decode('cp1252', 'replace')
        m = re.search(r'COPYRIGHT="(.*?)"', comment)
        if m:
            mi.rights = m.group(1).strip().decode('cp1252', 'replace')
        m = re.search(r'ISBN="(.*?)"', comment)
        if m:
            mi.isbn = m.group(1).strip().decode('cp1252', 'replace')

    return mi
