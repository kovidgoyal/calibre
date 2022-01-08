__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'

'''
Read meta information from TXT files
'''

import re, os

from calibre.ebooks.metadata import MetaInformation


def get_metadata(stream, extract_cover=True):
    '''
    Return metadata as a L{MetaInfo} object
    '''
    name = getattr(stream, 'name', '').rpartition('.')[0]
    if name:
        name = os.path.basename(name)
    mi = MetaInformation(name or _('Unknown'), [_('Unknown')])
    stream.seek(0)

    mdata = ''
    for x in range(0, 4):
        line = stream.readline().decode('utf-8', 'replace')
        if not line:
            break
        else:
            mdata += line

    mdata = mdata[:1024]

    mo = re.search('(?u)^[ ]*(?P<title>.+)[ ]*(\n{3}|(\r\n){3}|\r{3})[ ]*(?P<author>.+)[ ]*(\n|\r\n|\r)$', mdata)
    if mo is not None:
        mi.title = mo.group('title')
        mi.authors = mo.group('author').split(',')

    return mi
