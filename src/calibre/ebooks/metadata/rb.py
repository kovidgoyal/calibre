__license__   = 'GPL v3'
__copyright__ = '2008, Ashish Kulkarni <kulkarni.ashish@gmail.com>'
'''Read meta information from RB files'''

import sys, struct

from calibre.ebooks.metadata import MetaInformation, string_to_authors

MAGIC = '\xb0\x0c\xb0\x0c\x02\x00NUVO\x00\x00\x00\x00'

def get_metadata(stream):
    """ Return metadata as a L{MetaInfo} object """
    title = 'Unknown'
    mi = MetaInformation(title, ['Unknown'])
    stream.seek(0)
    try:
        if not stream.read(14) == MAGIC:
            print >>sys.stderr, u'Couldn\'t read RB header from file'
            return mi
        stream.read(10)
        
        read_i32 = lambda: struct.unpack('<I', stream.read(4))[0]
        
        stream.seek(read_i32())
        toc_count = read_i32()

        for i in range(toc_count):
            stream.read(32)
            length, offset, flag = read_i32(), read_i32(), read_i32()
            if flag == 2: break
        else:
            print >>sys.stderr, u'Couldn\'t find INFO from RB file'
            return mi
            
        stream.seek(offset)
        info = stream.read(length).splitlines()
        for line in info:
            if not '=' in line:
                continue
            key, value = line.split('=')
            if key.strip() == 'TITLE':
                mi.title = value.strip()
            elif key.strip() == 'AUTHOR':
                mi.author = value
                mi.authors = string_to_authors(value)
    except Exception as err:
        msg = u'Couldn\'t read metadata from rb: %s with error %s'%(mi.title, unicode(err))
        print >>sys.stderr, msg.encode('utf8')
        raise
    return mi
        
         
