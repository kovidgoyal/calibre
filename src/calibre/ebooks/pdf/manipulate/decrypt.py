# -*- coding: utf-8 -*-
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Decrypt content of PDF.
'''

import os, sys
from optparse import OptionGroup, Option

from calibre.utils.config import OptionParser
from calibre.utils.logging import Log
from calibre.constants import preferred_encoding
from calibre.customize.conversion import OptionRecommendation
from calibre.ebooks.pdf.verify import is_valid_pdf, is_encrypted

from pyPdf import PdfFileWriter, PdfFileReader

USAGE = '\n%prog %%name ' + _('''\
[options] file.pdf password

Decrypt a PDF.
''')

OPTIONS = set([
    OptionRecommendation(name='output', recommended_value='decrypted.pdf',
        level=OptionRecommendation.HIGH, long_switch='output', short_switch='o',
        help=_('Path to output file. By default a file is created in the current directory.')),
])

class DecryptionError(Exception):
    def __init__(self, pdf_path):
        self.value = 'Unable to decrypt file `%s`.' % pdf_path

    def __str__(self):
        return repr(self.value)


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
    group = OptionGroup(parser, _('Decrypt Options:'), _('Options to control the transformation of pdf'))
    parser.add_option_group(group)
    add_option = group.add_option

    for rec in OPTIONS:
        option_recommendation_to_cli_option(add_option, rec)

def decrypt(pdf_path, out_path, password):
    pdf = PdfFileReader(open(os.path.abspath(pdf_path), 'rb'))

    if pdf.decrypt(str(password)) == 0:
        raise DecryptionError(pdf_path)

    title = pdf.documentInfo.title if pdf.documentInfo.title else _('Unknown')
    author = pdf.documentInfo.author if pdf.documentInfo.author else _('Unknown')
    out_pdf = PdfFileWriter(title=title, author=author)

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
        print 'Error: A PDF file and decryption password is required.\n'
        print_help(parser, log)
        return 1

    if not is_valid_pdf(args[0]):
        print 'Error: Could not read file `%s`.' % args[0]
        return 1

    if not is_encrypted(args[0]):
        print 'Error: file `%s` is not encrypted.' % args[0]
        return 1

    try:
        decrypt(args[0], opts.output, args[1])
    except DecryptionError as e:
        print e.value
        return 1

    return 0

if __name__ == '__main__':
    sys.exit(main())
