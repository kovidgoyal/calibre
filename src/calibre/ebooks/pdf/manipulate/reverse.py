# -*- coding: utf-8 -*-
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Reverse content of PDF.
'''

import os, sys

from calibre.ebooks.metadata.meta import metadata_from_formats
from calibre.ebooks.metadata import authors_to_string
from calibre.utils.config import Config, StringConfig

from pyPdf import PdfFileWriter, PdfFileReader

def config(defaults=None):
    desc = _('Options to control the transformation of pdf')
    if defaults is None:
        c = Config('reversepdf', desc)
    else:
        c = StringConfig(defaults, desc)
    c.add_opt('output', ['-o', '--output'], default='reversed.pdf',
          help=_('Path to output file. By default a file is created in the current directory.'))
    return c

def option_parser(name):
    c = config()
    return c.option_parser(usage=_('''\
	%prog %%name [options] file1.pdf

	Reverse PDF.
	'''.replace('%%name', name)))

def reverse(pdf_path, out_path, metadata=None):
    if metadata == None:
        title = _('Unknown')
        author = _('Unknown')
    else:
        title = metadata.title
        author = authors_to_string(metadata.authors)

    out_pdf = PdfFileWriter(title=title, author=author)

    pdf = PdfFileReader(open(os.path.abspath(pdf_path), 'rb'))
    for page in reversed(pdf.pages):
        out_pdf.addPage(page)

    with open(out_path, 'wb') as out_file:
        out_pdf.write(out_file)

# Return True if the pdf is valid.
def valid_pdf(pdf_path):
    try:
        with open(os.path.abspath(pdf_path), 'rb') as pdf_file:
            pdf = PdfFileReader(pdf_file)
            if pdf.isEncrypted or pdf.numPages <= 0:
                raise Exception
    except:
        return False
    return True


def main(args=sys.argv, name=''):
    parser = option_parser(name)
    opts, args = parser.parse_args(args)
    args = args[1:]
    
    if len(args) < 1:
        print 'Error: A PDF file is required.\n\n'
        print parser.get_usage()
        return 2
    
    if not valid_pdf(args[0]):
        print 'Error: Could not read file `%s`. Is it a vaild PDF file or is it encrypted/DRMed?.' % args[0]
        return 2
    
    mi = metadata_from_formats([args[0]])

    reverse(args[0], opts.output, mi)

    return 0

if __name__ == '__main__':
    sys.exit(main())
