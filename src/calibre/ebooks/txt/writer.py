# -*- coding: utf-8 -*-
'''
Write content to TXT.
'''
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'

import os, logging, re, sys

from BeautifulSoup import BeautifulSoup

from calibre import LoggingInterface
from calibre.ebooks.htmlsymbols import HTML_SYMBOLS
from calibre.ebooks.epub.iterator import SpineItem
from calibre.ebooks.metadata import authors_to_string
from calibre.ebooks.metadata.meta import metadata_from_formats
from calibre.ebooks.metadata.opf2 import OPF
from calibre.customize.ui import run_plugins_on_postprocess
from calibre.utils.config import Config, StringConfig

class TXTWriter(object):
    def __init__(self, newline):
        self.newline = newline

    def dump(self, oebpath, path, metadata):
        opf = OPF(oebpath, os.path.dirname(oebpath))
        spine = [SpineItem(i.path) for i in opf.spine]

        tmpout = ''
        for item in spine:
            with open(item, 'r') as itemf:
                content = itemf.read().decode(item.encoding)
                # Convert newlines to unix style \n for processing. These
                # will be changed to the specified type later in the process.
                content = self.unix_newlines(content)
                content = self.strip_html(content)
                content = self.replace_html_symbols(content)
                content = self.cleanup_text(content)
                content = self.specified_newlines(content)
                tmpout = tmpout + content

        # Prepend metadata
        if metadata.author != None and metadata.author != '':
            tmpout = (u'%s%s%s%s' % (metadata.author.upper(), self.newline, self.newline, self.newline)) + tmpout
        if metadata.title != None and metadata.title != '':
            tmpout = (u'%s%s%s%s' % (metadata.title.upper(), self.newline, self.newline, self.newline)) + tmpout

            # Put two blank lines at end of file

            end = tmpout[-3 * len(self.newline):]
            for i in range(3 - end.count(self.newline)):
                tmpout = tmpout + self.newline

        if os.path.exists(path):
            os.remove(path)
        with open(path, 'w+b') as out:
            out.write(tmpout.encode('utf-8'))
            
    def strip_html(self, html):
        stripped = u''
        
        for dom_tree in BeautifulSoup(html).findAll('body'):
            text = unicode(dom_tree)
            
            # Remove unnecessary tags
            for tag in ['script', 'style']:
                text = re.sub('(?imu)<[ ]*%s[ ]*.*?>(.*)</[ ]*%s[ ]*>' % (tag, tag), '', text)
            text = re.sub('<!--.*-->', '', text)

            # Headings usually indicate Chapters.
            # We are going to use a marker to insert the proper number of
            # newline characters at the end of cleanup_text because cleanup_text
            # remove excessive (more than 2 newlines).
            for tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                text = re.sub('(?imu)<[ ]*%s[ ]*.*?>' % tag, '-vzxedxy-', text)
                text = re.sub('(?imu)</[ ]*%s[ ]*>' % tag, '-vlgzxey-', text)

            # Separate content with space.
            for tag in ['td']:
                text = re.sub('(?imu)</[ ]*%s[ ]*>', ' ', text)
            
            # Separate content with empty line.
            for tag in ['p', 'div', 'pre', 'li', 'table', 'tr']:
                text = re.sub('(?imu)</[ ]*%s[ ]*>' % tag, '\n\n', text)
            
            for tag in ['hr', 'br']:
                text = re.sub('(?imu)<[ ]*%s[ ]*/*?>' % tag, '\n\n', text)
            
            # Remove any tags that do not need special processing.
            text = re.sub('<.*?>', '', text)
            
            stripped = stripped + text
            
        return stripped
        
    def replace_html_symbols(self, content):
        for symbol in HTML_SYMBOLS:
            for code in HTML_SYMBOLS[symbol]:
                content = content.replace(code, symbol)
        return content
        
    def cleanup_text(self, text):
        # Replace bad characters.
        text = text.replace(u'\xc2', '')
        text = text.replace(u'\xa0', ' ')
    
        # Replace tabs, vertical tags and form feeds with single space.
        #text = re.sub('\xc2\xa0', '', text)
        text = text.replace('\t+', ' ')
        text = text.replace('\v+', ' ')
        text = text.replace('\f+', ' ')
    
        # Single line paragraph.
        r = re.compile('.\n.')
        while True:
            mo = r.search(text)
            if mo == None:
                break
            text = '%s %s' % (text[:mo.start()+1], text[mo.end()-1:])
        
        # Remove multiple spaces.
        text = re.sub('[  ]+', ' ', text)
        text = re.sub('(?imu)^[ ]+', '', text)
        text = re.sub('(?imu)[ ]+$', '', text)
        
        # Remove excessive newlines.
        text = re.sub('\n[ ]+\n', '\n\n', text)
        text = re.sub('\n{3,}', '\n\n', text)
        
        # Replace markers with the proper characters.
        text = text.replace('-vzxedxy-', '\n\n\n\n\n')
        text = text.replace('-vlgzxey-', '\n\n\n')
        
        return text

    def unix_newlines(self, text):
        text = text.replace('\r\n', '\n')
        text = text.replace('\r', '\n')
        
        return text
        
    def specified_newlines(self, text):
        if self.newline == '\n':
            return text
        
        return text.replace('\n', self.newline)
        
class TxtMetadata(object):
    def __init__(self):
        self.author = None
        self.title = None
        self.series = None
        

class TxtNewlines(object):
    NEWLINE_TYPES = {
                        'system'  : os.linesep,
                        'unix'    : '\n',
                        'old_mac' : '\r',
                        'windows' : '\r\n'
                     }
                     
    def __init__(self, newline_type):
        self.newline = self.NEWLINE_TYPES.get(newline_type.lower(), os.linesep)


def config(defaults=None):
    desc = _('Options to control the conversion to TXT')
    if defaults is None:
        c = Config('txt', desc)
    else:
        c = StringConfig(defaults, desc)
        
    txt = c.add_group('TXT', _('TXT options.'))
            
    txt('newline', ['--newline'], default='system',
        help=_('Type of newline to use. Options are %s. Default is \'system\'. '
            'Use \'old_mac\' for compatibility with Mac OS 9 and earlier. '
            'For Mac OS X use \'unix\'. \'system\' will default to the newline '
            'type used by this OS.' % sorted(TxtNewlines.NEWLINE_TYPES.keys())))
    txt('prepend_author', ['--prepend-author'], default='true',
        help=_('Write the author to the beginning of the file. '
            'Default is \'true\'. Use \'false\' to disable.'))
    txt('prepend_title', ['--prepend-title'], default='true',
        help=_('Write the title to the beginning of the file. '
            'Default is \'true\'. Use \'false\' to disable.'))
        
    return c

def option_parser():
    c = config()
    parser = c.option_parser(usage='%prog '+_('[options]')+' file.opf')
    parser.add_option(
        '-o', '--output', default=None, 
        help=_('Output file. Default is derived from input filename.'))
    parser.add_option(
        '-v', '--verbose', default=0, action='count',
        help=_('Useful for debugging.'))        
    return parser

def oeb2txt(opts, inpath):
    logger = LoggingInterface(logging.getLogger('oeb2txt'))
    logger.setup_cli_handler(opts.verbose)
    
    outpath = opts.output
    if outpath is None:
        outpath = os.path.basename(inpath)
        outpath = os.path.splitext(outpath)[0] + '.txt'

    mi = metadata_from_formats([inpath])
    metadata = TxtMetadata()
    if opts.prepend_author.lower() == 'true':
        metadata.author = opts.authors if opts.authors else authors_to_string(mi.authors)
    if opts.prepend_title.lower() == 'true':
        metadata.title = opts.title if opts.title else mi.title

    newline = TxtNewlines(opts.newline)
    
    writer = TXTWriter(newline.newline)
    writer.dump(inpath, outpath, metadata)
    run_plugins_on_postprocess(outpath, 'txt')
    logger.log_info(_('Output written to ') + outpath)
    
def main(argv=sys.argv):
    parser = option_parser()
    opts, args = parser.parse_args(argv[1:])
    if len(args) != 1:
        parser.print_help()
        return 1
    inpath = args[0]
    retval = oeb2txt(opts, inpath)
    return retval

if __name__ == '__main__':
    sys.exit(main())

