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
            r'(?msu)/(?P<words>.+?)/',
            r'(?msu)~~(?P<words>.+?)~~',
            r'(?msu)\*(?P<words>.+?)\*',
            r'(?msu)~(?P<words>.+?)~',
            r'(?msu)_/(?P<words>.+?)/_',
            r'(?msu)_\*(?P<words>.+?)\*_',
            r'(?msu)\*/(?P<words>.+?)/\*',
            r'(?msu)_\*/(?P<words>.+?)/\*_',
            r'(?msu)/:(?P<words>.+?):/',
            r'(?msu)\|:(?P<words>.+?):\|',
        ]

    def del_maketrans(self, deletechars):
        return dict([(ord(x), u'') for x in deletechars])

    def is_heading(self, line):
        if not line:
            return False
        if len(line) > 40:
            return False
        
        line = Unidecoder().decode(line)

        # punctuation.
        if line.translate(self.del_maketrans(string.letters + string.digits + ' :-')):
            return False
        
        # All upper case.
        #if line.isupper():
        #    return True
        # Roman numerals.
        #if not line.translate(self.del_maketrans('IVXYCivxyc ')):
        #    return True
        
        return True

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
        last_was_heading = False
        for line in txt.split('\n\n'):
            if self.is_heading(line):
                if not last_was_heading:
                    processed.append(u'<h1>%s</h1>' % prepare_string_for_xml(line.replace('\n', ' ')))
                else:
                    processed.append(u'<h2>%s</h2>' % prepare_string_for_xml(line.replace('\n', ' ')))
                last_was_heading = True
            else:
                processed.append(u'<p>%s</p>' % self.process_paragraph(prepare_string_for_xml(line.replace('\n', ' '))))
                last_was_heading = False
                
        txt = u'\n'.join(processed)
        txt = re.sub('[ ]{2,}', ' ', txt)

        return HTML_TEMPLATE % (title, txt)
