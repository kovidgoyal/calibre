# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import re
import string

from calibre import prepare_string_for_xml
from calibre.ebooks.unidecode.unidecoder import Unidecoder

class TXTHeuristicProcessor(object):

    def __init__(self):
        self.ITALICIZE_WORDS = [
            'Etc.', 'etc.', 'viz.', 'ie.', 'i.e.', 'Ie.', 'I.e.', 'eg.',
            'e.g.', 'Eg.', 'E.g.', 'et al.', 'et cetra', 'n.b.', 'N.b.',
            'nota bene', 'Nota bene', 'Ste.', 'Mme.', 'Mdme.',
            'Mlle.', 'Mons.', 'PS.', 'PPS.', 
        ]
        self.ITALICIZE_STYLE_PATS = [
            r'(?msu)_(?P<words>.+?)_',
            r'(?msu)/(?P<words>[^<>]+?)/',
            r'(?msu)~~(?P<words>.+?)~~',
            r'(?msu)\*(?P<words>.+?)\*',
            r'(?msu)~(?P<words>.+?)~',
            r'(?msu)_/(?P<words>[^<>]+?)/_',
            r'(?msu)_\*(?P<words>.+?)\*_',
            r'(?msu)\*/(?P<words>[^<>]+?)/\*',
            r'(?msu)_\*/(?P<words>[^<>]+?)/\*_',
            r'(?msu)/:(?P<words>[^<>]+?):/',
            r'(?msu)\|:(?P<words>.+?):\|',
        ]

    def process_paragraph(self, paragraph):
        for word in self.ITALICIZE_WORDS:
            paragraph = paragraph.replace(word, '<i>%s</i>' % word)
        for pat in self.ITALICIZE_STYLE_PATS:
            paragraph = re.sub(pat, lambda mo: '<i>%s</i>' % mo.group('words'), paragraph)
        return paragraph

    def convert(self, txt, title='', epub_split_size_kb=0):
        from calibre.ebooks.txt.processor import clean_txt, split_txt, HTML_TEMPLATE
        txt = clean_txt(txt)
        txt = split_txt(txt, epub_split_size_kb)
        
        processed = []
        for line in txt.split('\n\n'):
            processed.append(u'<p>%s</p>' % self.process_paragraph(prepare_string_for_xml(line.replace('\n', ' '))))
                
        txt = u'\n'.join(processed)
        txt = re.sub('[ ]{2,}', ' ', txt)
        html = HTML_TEMPLATE % (title, txt)
        
        from calibre.ebooks.conversion.utils import PreProcessor
        pp = PreProcessor()
        html = pp.markup_chapters(html, pp.get_word_count(html), False)

        return html
