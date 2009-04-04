from __future__ import with_statement
# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Merge PDF files into a single PDF document.
'''

import os, re, sys, time
from optparse import OptionGroup, Option

from calibre.utils.config import OptionParser
from calibre.utils.logging import Log
from calibre.constants import preferred_encoding
from calibre.customize.conversion import OptionRecommendation
from calibre.ebooks.pdf.verify import is_valid_pdfs, is_encrypted

from pyPdf import PdfFileWriter, PdfFileReader

USAGE = '\n%prog %%name ' + _('''\
file.pdf ...

Get info about a PDF.
''')

def print_help(parser, log):
    help = parser.format_help().encode(preferred_encoding, 'replace')
    log(help)

def option_parser(name):
    usage = USAGE.replace('%%name', name)
    return OptionParser(usage=usage)

def print_info(pdf_path):
    with open(os.path.abspath(pdf_path), 'rb') as pdf_file:
        pdf = PdfFileReader(pdf_file)
        print _('Title:                 %s' % pdf.documentInfo.title)
        print _('Author:                %s' % pdf.documentInfo.author)
        print _('Subject:               %s' % pdf.documentInfo.subject)
        print _('Creator:               %s' % pdf.documentInfo.creator)
        print _('Producer:              %s' % pdf.documentInfo.producer)
        print _('Creation Date:         %s' % time.strftime('%a %b %d %H:%M:%S %Y', time.gmtime(os.path.getctime(pdf_path))))
        print _('Modification Date:     %s' % time.strftime('%a %b %d %H:%M:%S %Y', time.gmtime(os.path.getmtime(pdf_path))))
        print _('Pages:                 %s' % pdf.numPages)
        print _('Encrypted:             %s' % pdf.isEncrypted)
        try:
            print _('File Size:             %s bytes' % os.path.getsize(pdf_path))
        except: pass
        try:
            pdf_file.seek(0)
            vline = pdf_file.readline()
            mo = re.search('(?iu)^%...-(?P<version>\d+\.\d+)', vline)
            if mo != None:
                print _('PDF Version:           %s' % mo.group('version'))
        except: pass

def main(args=sys.argv, name=''):
    log = Log()
    parser = option_parser(name)
    
    opts, args = parser.parse_args(args)
    args = args[1:]
    
    if len(args) < 1:
        print 'Error: No PDF sepecified.\n'
        print_help(parser, log)
        return 1
    
    bad_pdfs = is_valid_pdfs(args)
    if bad_pdfs != []:
        for pdf in bad_pdfs:
            print 'Error: Could not read file `%s`.' % pdf
        return 1

    enc = False
    for pdf in args:
        if is_encrypted(pdf):
            enc = True
            print 'Error: file `%s` is encrypted. Please decrypt first.' % pdf
    if enc:
        return 1

    for pdf in args:
        print_info(pdf)
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
