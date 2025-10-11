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

    print(f'Header Size:     {len(h0)}')

    if len(h0) == 132:
        print('Header Type:     Dropbook compatible')
        print()
        ereader_header_info132(h0)
    elif len(h0) == 202:
        print('Header Type:     Makebook compatible')
        print()
        ereader_header_info202(h0)
    else:
        raise EreaderError(f'Size mismatch. eReader header record size {len(h0)} KB is not supported.')


def pdb_header_info(header):
    print('PDB Header Info:')
    print()
    print(f'Identity:        {header.ident}')
    print(f'Total Sections:   {header.num_sections}')
    print(f'Title:           {header.title}')
    print()


def ereader_header_info132(h0):
    print('Ereader Record 0 (Header) Info:')
    print()
    print(f"0-2 Version:             {struct.unpack('>H', h0[0:2])[0]}")
    print(f"2-4:                     {struct.unpack('>H', h0[2:4])[0]}")
    print(f"4-6:                     {struct.unpack('>H', h0[4:6])[0]}")
    print(f"6-8 Codepage:            {struct.unpack('>H', h0[6:8])[0]}")
    print(f"8-10:                    {struct.unpack('>H', h0[8:10])[0]}")
    print(f"10-12:                   {struct.unpack('>H', h0[10:12])[0]}")
    print(f"12-14 Non-Text offset:   {struct.unpack('>H', h0[12:14])[0]}")
    print(f"14-16:                   {struct.unpack('>H', h0[14:16])[0]}")
    print(f"16-18:                   {struct.unpack('>H', h0[16:18])[0]}")
    print(f"18-20:                   {struct.unpack('>H', h0[18:20])[0]}")
    print(f"20-22 Image Count:       {struct.unpack('>H', h0[20:22])[0]}")
    print(f"22-24:                   {struct.unpack('>H', h0[22:24])[0]}")
    print(f"24-26 Has Metadata?:     {struct.unpack('>H', h0[24:26])[0]}")
    print(f"26-28:                   {struct.unpack('>H', h0[26:28])[0]}")
    print(f"28-30 Footnote Count:    {struct.unpack('>H', h0[28:30])[0]}")
    print(f"30-32 Sidebar Count:     {struct.unpack('>H', h0[30:32])[0]}")
    print(f"32-34 Bookmark Offset:   {struct.unpack('>H', h0[32:34])[0]}")
    print(f"34-36 MAGIC:             {struct.unpack('>H', h0[34:36])[0]}")
    print(f"36-38:                   {struct.unpack('>H', h0[36:38])[0]}")
    print(f"38-40:                   {struct.unpack('>H', h0[38:40])[0]}")
    print(f"40-42 Image Data Offset: {struct.unpack('>H', h0[40:42])[0]}")
    print(f"42-44:                   {struct.unpack('>H', h0[42:44])[0]}")
    print(f"44-46 Metadata Offset:   {struct.unpack('>H', h0[44:46])[0]}")
    print(f"46-48:                   {struct.unpack('>H', h0[46:48])[0]}")
    print(f"48-50 Footnote Offset:   {struct.unpack('>H', h0[48:50])[0]}")
    print(f"50-52 Sidebar Offset:    {struct.unpack('>H', h0[50:52])[0]}")
    print(f"52-54 Last Data Offset:  {struct.unpack('>H', h0[52:54])[0]}")

    for i in range(54, 131, 2):
        print(f"{i}-{i + 2}:                   {struct.unpack('>H', h0[i:i + 2])[0]}")

    print()


def ereader_header_info202(h0):
    print('Ereader Record 0 (Header) Info:')
    print()
    print(f"0-2 Version:             {struct.unpack('>H', h0[0:2])[0]}")
    print(f"2-4 Garbage:             {struct.unpack('>H', h0[2:4])[0]}")
    print(f"4-6 Garbage:             {struct.unpack('>H', h0[4:6])[0]}")
    print(f"6-8 Garbage:             {struct.unpack('>H', h0[6:8])[0]}")
    print(f"8-10 Non-Text Offset:    {struct.unpack('>H', h0[8:10])[0]}")
    print(f"10-12:                   {struct.unpack('>H', h0[10:12])[0]}")
    print(f"12-14:                   {struct.unpack('>H', h0[12:14])[0]}")
    print(f"14-16 Garbage:           {struct.unpack('>H', h0[14:16])[0]}")
    print(f"16-18 Garbage:           {struct.unpack('>H', h0[16:18])[0]}")
    print(f"18-20 Garbage:           {struct.unpack('>H', h0[18:20])[0]}")
    print(f"20-22 Garbage:           {struct.unpack('>H', h0[20:22])[0]}")
    print(f"22-24 Garbage:           {struct.unpack('>H', h0[22:24])[0]}")
    print(f"24-26:                   {struct.unpack('>H', h0[24:26])[0]}")
    print(f"26-28:                   {struct.unpack('>H', h0[26:28])[0]}")
    for i in range(28, 98, 2):
        print(f"{i}-{i + 2} Garbage:           {struct.unpack('>H', h0[i:i + 2])[0]}")
    print(f"98-100:                  {struct.unpack('>H', h0[98:100])[0]}")
    for i in range(100, 110, 2):
        print(f"{i}-{i + 2} Garbage:         {struct.unpack('>H', h0[i:i + 2])[0]}")
    print(f"110-112:                 {struct.unpack('>H', h0[110:112])[0]}")
    print(f"112-114:                 {struct.unpack('>H', h0[112:114])[0]}")
    print(f"114-116 Garbage:         {struct.unpack('>H', h0[114:116])[0]}")
    for i in range(116, 202, 2):
        print(f"{i}-{i + 2}:                 {struct.unpack('>H', h0[i:i + 2])[0]}")

    print()
    print('* Garbage: Random values.')
    print()


def section_lengths(header):
    print('Section Sizes')
    print()

    for i in range(header.section_count()):
        size = len(header.section_data(i))
        if size > 65505:
            message = '<--- Over!'
        else:
            message = ''

        print(f'Section {i}:   {size} {message}')


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
