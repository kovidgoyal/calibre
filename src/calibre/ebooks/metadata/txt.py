'''Read meta information from TXT files'''

from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'

import re

from calibre.ebooks.metadata import MetaInformation

def get_metadata(stream, extract_cover=True):
    """ Return metadata as a L{MetaInfo} object """
    mi = MetaInformation(_('Unknown'), [_('Unknown')])
    stream.seek(0)

    mdata = ''
    for x in range(0, 4):
        line = stream.readline()
        if line == '':
            break
        else:
            mdata += line
    
    mo = re.search('(?u)^[ ]*(?P<title>.+)[ ]*\n\n\n[ ]*(?P<author>.+)[ ]*\n$', mdata)
    if mo != None:
        mi.title = mo.group('title')
        mi.authors = mo.group('author').split(',')

    return mi
