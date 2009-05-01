# -*- coding: utf-8 -*-
'''
Inspect the header of ereader files. This is primarily used for debugging.
'''

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import struct, sys

from calibre.ebooks.pdb.header import PdbHeaderReader
from calibre.ebooks.pdb.ereader.reader import HeaderRecord

def pdb_header_info(header):
    print 'PDB Header Info:'
    print ''
    print 'Identity:        %s' % header.ident
    print 'Total Sectons:   %s' % header.num_sections
    print 'Title:           %s' % header.title
    print ''

def ereader_header_info(header):    
    h0 = header.section_data(0)
    
    print 'Ereader Record 0 (Header) Info:'
    print ''
    print '0-2 Version:             %i' % struct.unpack('>H', h0[0:2])[0]
    print '2-4:                     %i' % struct.unpack('>H', h0[2:4])[0]
    print '4-6:                     %i' % struct.unpack('>H', h0[4:6])[0]
    print '6-8:                     %i' % struct.unpack('>H', h0[6:8])[0]
    print '8-10:                    %i' % struct.unpack('>H', h0[8:10])[0]
    print '10-12:                   %i' % struct.unpack('>H', h0[10:12])[0]
    print '12-14 Non-Text:          %i' % struct.unpack('>H', h0[12:14])[0]
    print '14-16:                   %i' % struct.unpack('>H', h0[14:16])[0]
    print '16-18:                   %i' % struct.unpack('>H', h0[16:18])[0]
    print '18-20:                   %i' % struct.unpack('>H', h0[18:20])[0]
    print '20-22:                   %i' % struct.unpack('>H', h0[20:22])[0]
    print '22-24:                   %i' % struct.unpack('>H', h0[22:24])[0]
    print '24-26:                   %i' % struct.unpack('>H', h0[24:26])[0]
    print '26-28:                   %i' % struct.unpack('>H', h0[26:28])[0]
    print '28-30 footnote_rec:      %i' % struct.unpack('>H', h0[28:30])[0]
    print '30-32 sidebar_rec:       %i' % struct.unpack('>H', h0[30:32])[0]
    print '32-34 bookmark_offset:   %i' % struct.unpack('>H', h0[32:34])[0]
    print '34-36:                   %i' % struct.unpack('>H', h0[34:36])[0]
    print '36-38:                   %i' % struct.unpack('>H', h0[36:38])[0]
    print '38-40:                   %i' % struct.unpack('>H', h0[38:40])[0]
    print '40-42 image_data_offset: %i' % struct.unpack('>H', h0[40:42])[0]
    print '42-44:                   %i' % struct.unpack('>H', h0[42:44])[0]
    print '44-46 metadata_offset:   %i' % struct.unpack('>H', h0[44:46])[0]
    print '46-48:                   %i' % struct.unpack('>H', h0[46:48])[0]
    print '48-50 footnote_offset:   %i' % struct.unpack('>H', h0[48:50])[0]
    print '50-52 sidebar_offset:    %i' % struct.unpack('>H', h0[50:52])[0]
    print '52-54 last_data_offset:  %i' % struct.unpack('>H', h0[52:54])[0]
    
    for i in range(54, 131, 2):
        print '%i-%i:                   %i' % (i, i+2, struct.unpack('>H', h0[i:i+2])[0])
    
    print ''
    
def section_lengths(header):
    print 'Section Sizes'
    print ''
    
    for i in range(0, header.section_count()):
        size = len(header.section_data(i))
        if size > 65505:
            message = '<--- Over!'
        else:
            message = ''
        
        print 'Section %i:   %i %s' % (i, size, message)

def main(args=sys.argv):
    if len(args) < 2:
        print 'Error: requires input file.'
        return 1
    
    f = open(sys.argv[1], 'rb')
    
    pheader = PdbHeaderReader(f)
    
    pdb_header_info(pheader)
    ereader_header_info(pheader)
    section_lengths(pheader)
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
