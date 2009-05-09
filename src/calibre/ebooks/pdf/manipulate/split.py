# -*- coding: utf-8 -*-
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Split PDF file into multiple PDF documents.
'''

import os, sys, re
from optparse import OptionGroup, Option

from calibre.ebooks.metadata.meta import metadata_from_formats
from calibre.ebooks.metadata import authors_to_string
from calibre.utils.config import OptionParser
from calibre.utils.logging import Log
from calibre.constants import preferred_encoding
from calibre.customize.conversion import OptionRecommendation
from calibre.ebooks.pdf.verify import is_valid_pdf, is_encrypted

from pyPdf import PdfFileWriter, PdfFileReader

USAGE = _('''
%prog %%name [options] file.pdf page_to_split_on ...
%prog %%name [options] file.pdf page_range_to_split_on ...
	
Ex.
	
%prog %%name file.pdf 6
%prog %%name file.pdf 6-12
%prog %%name file.pdf 6-12 8 10 9-20

Split a PDF.
''')

OPTIONS = set([
    OptionRecommendation(name='output', recommended_value='split.pdf',
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
    group = OptionGroup(parser, _('Split Options:'), _('Options to control the transformation of pdf'))
    parser.add_option_group(group)
    add_option = group.add_option
    
    for rec in OPTIONS:
        option_recommendation_to_cli_option(add_option, rec)

def split_pdf(in_path, pages, page_ranges, out_name, metadata=None):
    pdf = PdfFileReader(open(os.path.abspath(in_path), 'rb'))
    total_pages = pdf.numPages - 1

    for index in pages+page_ranges:
        if index in pages:
            write_pdf(pdf, out_name, '%s' % (index + 1), index, total_pages, metadata)
        else:
            
            write_pdf(pdf, out_name, '%s-%s' % (index[0] + 1, index[1] + 1), index[0], index[1], metadata)
        
def write_pdf(pdf, name, suffix, start, end, metadata=None):
    if metadata == None:
        title = _('Unknown')
        author = _('Unknown')
    else:
        title = metadata.title
        author = authors_to_string(metadata.authors)
    
    out_pdf = PdfFileWriter(title=title, author=author)
    for page_num in range(start, end + 1):
        out_pdf.addPage(pdf.getPage(page_num))
    with open('%s%s.pdf' % (name, suffix), 'wb') as out_file:
        out_pdf.write(out_file)
    
def split_args(args):
    pdf = ''
    pages = []
    page_ranges = []
    bad = []

    for arg in args:
        arg = arg.strip()
        # Find the pdf input
        if re.search('(?iu)^.*?\.pdf[ ]*$', arg) != None:
            if pdf == '':
                pdf = arg
            else:
                bad.append(arg)
        # Find single indexes
        elif re.search('^[ ]*\d+[ ]*$', arg) != None:
            pages.append(arg)
        # Find index ranges
        elif re.search('^[ ]*\d+[ ]*-[ ]*\d+[ ]*$', arg) != None:
            mo = re.search('^[ ]*(?P<start>\d+)[ ]*-[ ]*(?P<end>\d+)[ ]*$', arg)
            start = mo.group('start')
            end = mo.group('end')
            
            # check to see if the range is really a single index
            if start == end:
                pages.append(start)
            else:
                page_ranges.append([start, end])
        else:
            bad.append(arg)
        
    bad = sorted(list(set(bad)))
    
    return pdf, pages, page_ranges, bad

# Remove duplicates from pages and page_ranges.
# Set pages higher than the total number of pages in the pdf to the last page.
# Return pages and page_ranges as lists of ints.
def clean_page_list(pdf_path, pages, page_ranges):
    pdf = PdfFileReader(open(os.path.abspath(pdf_path), 'rb'))
    
    total_pages = pdf.numPages
    sorted_pages = []
    sorted_ranges = []

    for index in pages:
        index = int(index)
        if index > total_pages:
            sorted_pages.append(total_pages - 1)
        else:
            sorted_pages.append(index - 1)
    
    for start, end in page_ranges:
        start = int(start)
        end = int(end)
        
        if start > total_pages and end > total_pages:
            sorted_pages.append(total_pages - 1)
            continue
            
        if start > total_pages:
            start = total_pages
        if end > total_pages:
            end = total_pages
        page_range = sorted([start - 1, end - 1])
        if page_range not in sorted_ranges:
            sorted_ranges.append(page_range)
    
    # Remove duplicates and sort
    pages = sorted(list(set(sorted_pages)))
    page_ranges = sorted(sorted_ranges)
    
    return pages, page_ranges

def main(args=sys.argv, name=''):
    log = Log()
    parser = option_parser(name)
    add_options(parser)
    
    opts, args = parser.parse_args(args)
    
    pdf, pages, page_ranges, unknown = split_args(args[1:])
    
    if pdf == '' and (pages == [] or page_ranges == []):
        print 'Error: PDF and where to split is required.\n'
        print_help(parser, log)
        return 1
    
    if unknown != []:
        for arg in unknown:
            print 'Error: Unknown argument `%s`' % arg
        print_help(parser, log)
        return 1
    
    if not is_valid_pdf(pdf):
        print 'Error: Could not read file `%s`.' % pdf
        return 1
        
    if is_encrypted(pdf):
        print 'Error: file `%s` is encrypted.' % args[0]
        return 1
        
    pages, page_ranges = clean_page_list(pdf, pages, page_ranges)
        
    mi = metadata_from_formats([pdf])

    split_pdf(pdf, pages, page_ranges, os.path.splitext(opts.output)[0], mi)

    return 0

if __name__ == '__main__':
    sys.exit(main())
