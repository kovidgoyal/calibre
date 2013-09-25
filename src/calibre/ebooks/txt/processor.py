# -*- coding: utf-8 -*-
__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'


'''
Read content from txt file.
'''

import os, re

from calibre import prepare_string_for_xml, isbytestring
from calibre.ebooks.metadata.opf2 import OPFCreator

from calibre.ebooks.conversion.preprocess import DocAnalysis
from calibre.utils.cleantext import clean_ascii_chars

HTML_TEMPLATE = u'<html><head><meta http-equiv="Content-Type" content="text/html; charset=utf-8"/><title>%s </title></head><body>\n%s\n</body></html>'

def clean_txt(txt):
    '''
    Run transformations on the text to put it into
    consistent state.
    '''
    if isbytestring(txt):
        txt = txt.decode('utf-8', 'replace')
    # Strip whitespace from the end of the line. Also replace
    # all line breaks with \n.
    txt = '\n'.join([line.rstrip() for line in txt.splitlines()])

    # Replace whitespace at the beginning of the line with &nbsp;
    txt = re.sub('(?m)(?<=^)([ ]{2,}|\t+)(?=.)', '&nbsp;' * 4, txt)

    # Condense redundant spaces
    txt = re.sub('[ ]{2,}', ' ', txt)

    # Remove blank space from the beginning and end of the document.
    txt = re.sub('^\s+(?=.)', '', txt)
    txt = re.sub('(?<=.)\s+$', '', txt)
    # Remove excessive line breaks.
    txt = re.sub('\n{5,}', '\n\n\n\n', txt)
    # remove ASCII invalid chars : 0 to 8 and 11-14 to 24
    txt = clean_ascii_chars(txt)

    return txt

def split_txt(txt, epub_split_size_kb=0):
    '''
    Ensure there are split points for converting
    to EPUB. A misdetected paragraph type can
    result in the entire document being one giant
    paragraph. In this case the EPUB parser will not
    be able to determine where to split the file
    to accomidate the EPUB file size limitation
    and will fail.
    '''
    # Takes care if there is no point to split
    if epub_split_size_kb > 0:
        if isinstance(txt, unicode):
            txt = txt.encode('utf-8')
        length_byte = len(txt)
        # Calculating the average chunk value for easy splitting as EPUB (+2 as a safe margin)
        chunk_size = long(length_byte / (int(length_byte / (epub_split_size_kb * 1024)) + 2))
        # if there are chunks with a superior size then go and break
        if (len(filter(lambda x: len(x) > chunk_size, txt.split('\n\n')))) :
            txt = '\n\n'.join([split_string_separator(line, chunk_size)
                for line in txt.split('\n\n')])
    if isbytestring(txt):
        txt = txt.decode('utf-8')

    return txt

def convert_basic(txt, title='', epub_split_size_kb=0):
    '''
    Converts plain text to html by putting all paragraphs in
    <p> tags. It condense and retains blank lines when necessary.

    Requires paragraphs to be in single line format.
    '''
    txt = clean_txt(txt)
    txt = split_txt(txt, epub_split_size_kb)

    lines = []
    blank_count = 0
    # Split into paragraphs based on having a blank line between text.
    for line in txt.split('\n'):
        if line.strip():
            blank_count = 0
            lines.append(u'<p>%s</p>' % prepare_string_for_xml(line.replace('\n', ' ')))
        else:
            blank_count += 1
            if blank_count == 2:
                lines.append(u'<p>&nbsp;</p>')

    return HTML_TEMPLATE % (title, u'\n'.join(lines))

def convert_markdown(txt, title='', extensions=('footnotes', 'tables', 'toc')):
    from calibre.ebooks.conversion.plugins.txt_input import MD_EXTENSIONS
    from calibre.ebooks.markdown import Markdown
    extensions = [x.lower() for x in extensions if x.lower() in MD_EXTENSIONS]
    md = Markdown(
          extensions,
          safe_mode=False)
    return HTML_TEMPLATE % (title, md.convert(txt))

def convert_textile(txt, title=''):
    from calibre.ebooks.textile import textile
    html = textile(txt, encoding='utf-8')
    return HTML_TEMPLATE % (title, html)

def normalize_line_endings(txt):
    txt = txt.replace('\r\n', '\n')
    txt = txt.replace('\r', '\n')
    return txt

def separate_paragraphs_single_line(txt):
    txt = txt.replace('\n', '\n\n')
    return txt

def separate_paragraphs_print_formatted(txt):
    txt = re.sub(u'(?miu)^(?P<indent>\t+|[ ]{2,})(?=.)', lambda mo: '\n%s' % mo.group('indent'), txt)
    return txt

def separate_hard_scene_breaks(txt):
    def sep_break(line):
        if len(line.strip()) > 0:
            return '\n%s\n' % line
        else:
            return line
    txt = re.sub(u'(?miu)^[ \t-=~\/_]+$', lambda mo: sep_break(mo.group()), txt)
    return txt

def block_to_single_line(txt):
    txt = re.sub(r'(?<=.)\n(?=.)', ' ', txt)
    return txt

def preserve_spaces(txt):
    '''
    Replaces spaces multiple spaces with &nbsp; entities.
    '''
    txt = re.sub('(?P<space>[ ]{2,})', lambda mo: ' ' + ('&nbsp;' * (len(mo.group('space')) - 1)), txt)
    txt = txt.replace('\t', '&nbsp;&nbsp;&nbsp;&nbsp;')
    return txt

def remove_indents(txt):
    '''
    Remove whitespace at the beginning of each line.
    '''
    txt = re.sub('(?miu)^\s+', '', txt)
    return txt

def opf_writer(path, opf_name, manifest, spine, mi):
    opf = OPFCreator(path, mi)
    opf.create_manifest(manifest)
    opf.create_spine(spine)
    with open(os.path.join(path, opf_name), 'wb') as opffile:
        opf.render(opffile)

def split_string_separator(txt, size):
    '''
    Splits the text by putting \n\n at the point size.
    '''
    if len(txt) > size:
        txt = ''.join([re.sub(u'\.(?P<ends>[^.]*)$', '.\n\n\g<ends>',
            txt[i:i+size], 1) for i in
            xrange(0, len(txt), size)])
    return txt

def detect_paragraph_type(txt):
    '''
    Tries to determine the paragraph type of the document.

    block: Paragraphs are separated by a blank line.
    single: Each line is a paragraph.
    print: Each paragraph starts with a 2+ spaces or a tab
           and ends when a new paragraph is reached.
    unformatted: most lines have hard line breaks, few/no blank lines or indents

    returns block, single, print, unformatted
    '''
    txt = txt.replace('\r\n', '\n')
    txt = txt.replace('\r', '\n')
    txt_line_count = len(re.findall('(?mu)^\s*.+$', txt))

    # Check for hard line breaks - true if 55% of the doc breaks in the same region
    docanalysis = DocAnalysis('txt', txt)
    hardbreaks = docanalysis.line_histogram(.55)

    if hardbreaks:
        # Determine print percentage
        tab_line_count = len(re.findall('(?mu)^(\t|\s{2,}).+$', txt))
        print_percent = tab_line_count / float(txt_line_count)

        # Determine block percentage
        empty_line_count = len(re.findall('(?mu)^\s*$', txt))
        block_percent = empty_line_count / float(txt_line_count)

        # Compare the two types - the type with the larger number of instances wins
        # in cases where only one or the other represents the vast majority of the document neither wins
        if print_percent >= block_percent:
            if .15 <= print_percent <= .75:
                return 'print'
        elif .15 <= block_percent <= .75:
            return 'block'

        # Assume unformatted text with hardbreaks if nothing else matches
        return 'unformatted'

    # return single if hardbreaks is false
    return 'single'


def detect_formatting_type(txt):
    '''
    Tries to determine the formatting of the document.

    markdown: Markdown formatting is used.
    textile: Textile formatting is used.
    heuristic: When none of the above formatting types are
               detected heuristic is returned.
    '''
    # Keep a count of the number of format specific object
    # that are found in the text.
    markdown_count = 0
    textile_count = 0

    # Check for markdown
    # Headings
    markdown_count += len(re.findall('(?mu)^#+', txt))
    markdown_count += len(re.findall('(?mu)^=+$', txt))
    markdown_count += len(re.findall('(?mu)^-+$', txt))
    # Images
    markdown_count += len(re.findall('(?u)!\[.*?\](\[|\()', txt))
    # Links
    markdown_count += len(re.findall('(?u)^|[^!]\[.*?\](\[|\()', txt))

    # Check for textile
    # Headings
    textile_count += len(re.findall(r'(?mu)^h[1-6]\.', txt))
    # Block quote.
    textile_count += len(re.findall(r'(?mu)^bq\.', txt))
    # Images
    textile_count += len(re.findall(r'(?mu)(?<=\!)\S+(?=\!)', txt))
    # Links
    textile_count += len(re.findall(r'"[^"]*":\S+', txt))
    # paragraph blocks
    textile_count += len(re.findall(r'(?mu)^p(<|<>|=|>)?\. ', txt))

    # Decide if either markdown or textile is used in the text
    # based on the number of unique formatting elements found.
    if markdown_count > 5 or textile_count > 5:
        if markdown_count > textile_count:
            return 'markdown'
        else:
            return 'textile'

    return 'heuristic'
