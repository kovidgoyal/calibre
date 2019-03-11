from __future__ import print_function
__license__   = 'GPL v3'
__copyright__ = '2008, Ashish Kulkarni <kulkarni.ashish@gmail.com>'
'''Read meta information from IMP files'''

import sys

from calibre.ebooks.metadata import MetaInformation, string_to_authors
from polyglot.builtins import unicode_type

MAGIC = ['\x00\x01BOOKDOUG', '\x00\x02BOOKDOUG']


def get_metadata(stream):
    """ Return metadata as a L{MetaInfo} object """
    title = 'Unknown'
    mi = MetaInformation(title, ['Unknown'])
    stream.seek(0)
    try:
        if stream.read(10) not in MAGIC:
            print(u'Couldn\'t read IMP header from file', file=sys.stderr)
            return mi

        def cString(skip=0):
            result = ''
            while 1:
                data = stream.read(1)
                if data == '\x00':
                    if not skip:
                        return result
                    skip -= 1
                    result, data = '', ''
                result += data

        stream.read(38)  # skip past some uninteresting headers
        cString()
        category, title, author = cString(), cString(1), cString(2)

        if title:
            mi.title = title
        if author:
            mi.authors = string_to_authors(author)
            mi.author = author
        if category:
            mi.category = category
    except Exception as err:
        msg = u'Couldn\'t read metadata from imp: %s with error %s'%(mi.title, unicode_type(err))
        print(msg.encode('utf8'), file=sys.stderr)
    return mi
