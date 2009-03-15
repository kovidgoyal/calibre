from __future__ import with_statement
__license__ = 'GPL 3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

''' Read metadata from Amazon's topaz format '''

def read_record(raw, name):
    idx = raw.find(name)
    if idx > -1:
        length = ord(raw[idx+len(name)])
        return raw[idx+len(name)+1:idx+len(name)+1+length]

def get_metadata(stream):
    raw = stream.read(8*1024)
    if not raw.startswith('TPZ'):
        raise ValueError('Not a Topaz file')
    first = raw.find('metadata')
    if first < 0:
        raise ValueError('Invalid Topaz file')
    second = raw.find('metadata', first+10)
    if second < 0:
        raise ValueError('Invalid Topaz file')
    raw = raw[second:second+1000]
    authors = read_record(raw, 'Authors')
    if authors:
        authors = authors.decode('utf-8', 'replace').split(';')
    else:
        authors = [_('Unknown')]
    title = read_record(raw, 'Title')
    if title:
        title = title.decode('utf-8', 'replace')
    else:
        raise ValueError('No metadata in file')
    from calibre.ebooks.metadata import MetaInformation
    return MetaInformation(title, authors)

if __name__ == '__main__':
    import sys
    print get_metadata(open(sys.argv[1], 'rb'))