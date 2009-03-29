'''
Merge PDF files into a single PDF document.
'''
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os, re, sys, time

from calibre.utils.config import Config, StringConfig

from pyPdf import PdfFileWriter, PdfFileReader


def config(defaults=None):
    desc = _('Options to control the transformation of pdf')
    if defaults is None:
        c = Config('manipulatepdf', desc)
    else:
        c = StringConfig(defaults, desc)
    return c

def option_parser(name):
    c = config()
    return c.option_parser(usage=_('''\
	%prog %%name [options] file.pdf ...

	Get info about a PDF.
	'''.replace('%%name', name)))

def print_info(pdf_path):
    with open(os.path.abspath(pdf_path), 'rb') as pdf_file:
        pdf = PdfFileReader(pdf_file)
        print _('Title:                 %s' % pdf.documentInfo.title)
        print _('Author:                %s' % pdf.documentInfo.author)
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

def verify_files(files):
    invalid = []

    for pdf_path in files:
        try:
            with open(os.path.abspath(pdf_path), 'rb') as pdf_file:
                pdf = PdfFileReader(pdf_file)
        except:
            invalid.append(pdf_path)
    return invalid

def main(args=sys.argv, name=''):
    parser = option_parser(name)
    opts, args = parser.parse_args(args)
    args = args[1:]
    
    if len(args) < 1:
        print 'Error: No PDF sepecified.\n'
        print parser.get_usage()
        return 2
    
    bad_pdfs = verify_files(args)
    if bad_pdfs != []:
        for pdf in bad_pdfs:
            print 'Error: Could not read file `%s`. Is it a vaild PDF file or is it encrypted/DRMed?.' % pdf
        return 2
        
    for pdf in args:
        print_info(pdf)
    
    return 0

if __name__ == '__main__':
    sys.exit(main())

