from __future__ import with_statement
# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Merge PDF files into a single PDF document.
'''

import os, sys
from optparse import OptionGroup, Option

from calibre.ebooks.metadata.meta import metadata_from_formats
from calibre.ebooks.metadata import authors_to_string
from calibre.utils.config import OptionParser
from calibre.utils.logging import Log
from calibre.constants import preferred_encoding
from calibre.customize.conversion import OptionRecommendation
from calibre.ebooks.pdf.verify import is_valid_pdfs, is_encrypted

from pyPdf import PdfFileWriter, PdfFileReader

USAGE = '\n%prog %%name ' + _('''\
[options] file1.pdf file2.pdf ...

Metadata will be used from the first PDF specified.

Merges individual PDFs.
''')

OPTIONS = set([
    OptionRecommendation(name='output', recommended_value='merged.pdf',
        level=OptionRecommendation.HIGH, long_switch='output', short_switch='o',
        help=_('Path to output file. By default a file is created in the current directory.')),
])

def print_help(parser, log):
    help = parser.format_help().encode(preferred_encoding, 'replace')
    log(help)

def option_parser(name):
    usage = USAGE.replace('%%name', name)
    return OptionParser(usage=usage)

def option_recommendation_to_cli_option(add_option, rec):
    opt = rec.option
    switches = ['-'+opt.short_switch] if opt.short_switch else []
    switches.append('--'+opt.long_switch)
    attrs = dict(dest=opt.name, help=opt.help,
                     choices=opt.choices, default=rec.recommended_value)
    add_option(Option(*switches, **attrs))

def add_options(parser):
    group = OptionGroup(parser, _('Merge Options:'), _('Options to control the transformation of pdf'))
    parser.add_option_group(group)
    add_option = group.add_option

    for rec in OPTIONS:
        option_recommendation_to_cli_option(add_option, rec)

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

def main(args=sys.argv, name=''):
    log = Log()
    parser = option_parser(name)
    add_options(parser)

    opts, args = parser.parse_args(args)
    args = args[1:]

    if len(args) < 2:
        print 'Error: Two or more PDF files are required.\n'
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
            print 'Error: file `%s` is encrypted.' % pdf
    if enc:
        return 1

    mi = metadata_from_formats([args[0]])

    merge_files(args, opts.output, mi)

    return 0

if __name__ == '__main__':
    sys.exit(main())
