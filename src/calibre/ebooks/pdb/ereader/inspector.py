# -*- coding: utf-8 -*-
'''
Inspect the header of ereader files. This is primarily used for debugging.
'''


__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import struct
import sys

from calibre.ebooks.pdb.ereader import EreaderError
from calibre.ebooks.pdb.header import PdbHeaderReader


def ereader_header_info(header):
    h0 = header.section_data(0)

    print('Header Size:     %s' % len(h0))

    if len(h0) == 132:
        print('Header Type:     Dropbook compatible')
        print('')
        ereader_header_info132(h0)
    elif len(h0) == 202:
        print('Header Type:     Makebook compatible')
        print('')
        ereader_header_info202(h0)
    else:
        raise EreaderError('Size mismatch. eReader header record size %i KB is not supported.' % len(h0))


def pdb_header_info(header):
    print('PDB Header Info:')
    print('')
    print('Identity:        %s' % header.ident)
    print('Total Sectons:   %s' % header.num_sections)
    print('Title:           %s' % header.title)
    print('')


def ereader_header_info132(h0):
    print('Ereader Record 0 (Header) Info:')
    print('')
    print('0-2 Version:             %i' % struct.unpack('>H', h0[0:2])[0])
    print('2-4:                     %i' % struct.unpack('>H', h0[2:4])[0])
    print('4-6:                     %i' % struct.unpack('>H', h0[4:6])[0])
    print('6-8 Codepage:            %i' % struct.unpack('>H', h0[6:8])[0])
    print('8-10:                    %i' % struct.unpack('>H', h0[8:10])[0])
    print('10-12:                   %i' % struct.unpack('>H', h0[10:12])[0])
    print('12-14 Non-Text offset:   %i' % struct.unpack('>H', h0[12:14])[0])
    print('14-16:                   %i' % struct.unpack('>H', h0[14:16])[0])
    print('16-18:                   %i' % struct.unpack('>H', h0[16:18])[0])
    print('18-20:                   %i' % struct.unpack('>H', h0[18:20])[0])
    print('20-22 Image Count:       %i' % struct.unpack('>H', h0[20:22])[0])
    print('22-24:                   %i' % struct.unpack('>H', h0[22:24])[0])
    print('24-26 Has Metadata?:     %i' % struct.unpack('>H', h0[24:26])[0])
    print('26-28:                   %i' % struct.unpack('>H', h0[26:28])[0])
    print('28-30 Footnote Count:    %i' % struct.unpack('>H', h0[28:30])[0])
    print('30-32 Sidebar Count:     %i' % struct.unpack('>H', h0[30:32])[0])
    print('32-34 Bookmark Offset:   %i' % struct.unpack('>H', h0[32:34])[0])
    print('34-36 MAGIC:             %i' % struct.unpack('>H', h0[34:36])[0])
    print('36-38:                   %i' % struct.unpack('>H', h0[36:38])[0])
    print('38-40:                   %i' % struct.unpack('>H', h0[38:40])[0])
    print('40-42 Image Data Offset: %i' % struct.unpack('>H', h0[40:42])[0])
    print('42-44:                   %i' % struct.unpack('>H', h0[42:44])[0])
    print('44-46 Metadata Offset:   %i' % struct.unpack('>H', h0[44:46])[0])
    print('46-48:                   %i' % struct.unpack('>H', h0[46:48])[0])
    print('48-50 Footnote Offset:   %i' % struct.unpack('>H', h0[48:50])[0])
    print('50-52 Sidebar Offset:    %i' % struct.unpack('>H', h0[50:52])[0])
    print('52-54 Last Data Offset:  %i' % struct.unpack('>H', h0[52:54])[0])

    for i in range(54, 131, 2):
        print('%i-%i:                   %i' % (i, i+2, struct.unpack('>H', h0[i:i+2])[0]))

    print('')


def ereader_header_info202(h0):
    print('Ereader Record 0 (Header) Info:')
    print('')
    print('0-2 Version:             %i' % struct.unpack('>H', h0[0:2])[0])
    print('2-4 Garbage:             %i' % struct.unpack('>H', h0[2:4])[0])
    print('4-6 Garbage:             %i' % struct.unpack('>H', h0[4:6])[0])
    print('6-8 Garbage:             %i' % struct.unpack('>H', h0[6:8])[0])
    print('8-10 Non-Text Offset:    %i' % struct.unpack('>H', h0[8:10])[0])
    print('10-12:                   %i' % struct.unpack('>H', h0[10:12])[0])
    print('12-14:                   %i' % struct.unpack('>H', h0[12:14])[0])
    print('14-16 Garbage:           %i' % struct.unpack('>H', h0[14:16])[0])
    print('16-18 Garbage:           %i' % struct.unpack('>H', h0[16:18])[0])
    print('18-20 Garbage:           %i' % struct.unpack('>H', h0[18:20])[0])
    print('20-22 Garbage:           %i' % struct.unpack('>H', h0[20:22])[0])
    print('22-24 Garbage:           %i' % struct.unpack('>H', h0[22:24])[0])
    print('24-26:                   %i' % struct.unpack('>H', h0[24:26])[0])
    print('26-28:                   %i' % struct.unpack('>H', h0[26:28])[0])
    for i in range(28, 98, 2):
        print('%i-%i Garbage:           %i' % (i, i+2, struct.unpack('>H', h0[i:i+2])[0]))
    print('98-100:                  %i' % struct.unpack('>H', h0[98:100])[0])
    for i in range(100, 110, 2):
        print('%i-%i Garbage:         %i' % (i, i+2, struct.unpack('>H', h0[i:i+2])[0]))
    print('110-112:                 %i' % struct.unpack('>H', h0[110:112])[0])
    print('112-114:                 %i' % struct.unpack('>H', h0[112:114])[0])
    print('114-116 Garbage:         %i' % struct.unpack('>H', h0[114:116])[0])
    for i in range(116, 202, 2):
        print('%i-%i:                 %i' % (i, i+2, struct.unpack('>H', h0[i:i+2])[0]))

    print('')
    print('* Garbage: Random values.')
    print('')


def section_lengths(header):
    print('Section Sizes')
    print('')

    for i in range(0, header.section_count()):
        size = len(header.section_data(i))
        if size > 65505:
            message = '<--- Over!'
        else:
            message = ''

        print('Section %i:   %i %s' % (i, size, message))


def main(args=sys.argv):
    if len(args) < 2:
        print('Error: requires input file.')
        return 1

    f = open(sys.argv[1], 'rb')

    pheader = PdbHeaderReader(f)

    pdb_header_info(pheader)
    ereader_header_info(pheader)
    section_lengths(pheader)

    return 0


if __name__ == '__main__':
    sys.exit(main())
