'''
Merge PDF files into a single PDF document.
'''
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os, sys

from calibre.ebooks.metadata.meta import metadata_from_formats
from calibre.ebooks.metadata import authors_to_string
from calibre.utils.config import Config, StringConfig

from pyPdf import PdfFileWriter, PdfFileReader

def config(defaults=None):
    desc = _('Options to control the transformation of pdf')
    if defaults is None:
        c = Config('mergepdf', desc)
    else:
        c = StringConfig(defaults, desc)
    c.add_opt('verbose', ['-v', '--verbose'], default=0, action='count',
          help=_('Be verbose, useful for debugging. Can be specified multiple times for greater verbosity.'))
    c.add_opt('output', ['-o', '--output'], default='merged.pdf',
          help=_('Path to output file. By default a file is created in the current directory.'))
    return c

def option_parser(name):
    c = config()
    return c.option_parser(usage=_('''\
	%prog %%name [options] file1.pdf file2.pdf ...

	Merges individual PDFs. Metadata will be used from the first PDF specified.
	'''.replace('%%name', name)))

def merge_files(in_paths, out_path, metadata=None):
    if metadata == None:
        title = _('Unknown')
        author = _('Unknown')
    else:
        title = metadata.title
        author = authors_to_string(metadata.authors)

    out_pdf = PdfFileWriter(title=title, author=author)

    for pdf_path in in_paths:
        pdf = PdfFileReader(open(os.path.abspath(pdf_path), 'rb'))
        for page in pdf.pages:
            out_pdf.addPage(page)

    with open(out_path, 'wb') as out_file:
        out_pdf.write(out_file)
    
def verify_files(files):
    invalid = []

    for pdf_path in files:
        try:
            with open(os.path.abspath(pdf_path), 'rb') as pdf_file:
                pdf = PdfFileReader(pdf_file)
                if pdf.isEncrypted or pdf.numPages <= 0:
                    raise Exception
        except:
            invalid.append(pdf_path)
    return invalid

def main(args=sys.argv, name=''):
    parser = option_parser(name)
    opts, args = parser.parse_args(args)
    args = args[1:]
    
    if len(args) < 2:
        print 'Error: Two or more PDF files are required.\n\n'
        print parser.get_usage()
        return 2
    
    bad_pdfs = verify_files(args)
    if bad_pdfs != []:
        for pdf in bad_pdfs:
            print 'Error: Could not read file `%s`. Is it a vaild PDF file or is it encrypted/DRMed?.' % pdf
        return 2
        
    mi = metadata_from_formats([args[0]])

    merge_files(args, opts.output, mi)

    return 0

if __name__ == '__main__':
    sys.exit(main())

