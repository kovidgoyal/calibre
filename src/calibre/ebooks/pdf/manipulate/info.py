from __future__ import with_statement
# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Merge PDF files into a single PDF document.
'''

import os, sys

from calibre.utils.config import OptionParser
from calibre.utils.logging import Log
from calibre.constants import preferred_encoding, plugins
from calibre.ebooks.pdf.verify import is_valid_pdfs, is_encrypted
from calibre import prints

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
    podofo, podofo_err = plugins['podofo']
    if not podofo:
        raise RuntimeError('Failed to load PoDoFo with error:'+podofo_err)
    p = podofo.PDFDoc()
    p.open(pdf_path)

    fmt = lambda x, y: '%-20s: %s'%(x, y)

    print

    prints(fmt(_('Title'), p.title))
    prints(fmt(_('Author'), p.author))
    prints(fmt(_('Subject'), p.subject))
    prints(fmt(_('Creator'), p.creator))
    prints(fmt(_('Producer'), p.producer))
    prints(fmt(_('Pages'), p.pages))
    prints(fmt(_('File Size'), os.stat(pdf_path).st_size))
    prints(fmt(_('PDF Version'), p.version if p.version else _('Unknown')))

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
