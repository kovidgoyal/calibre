__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

import re


class PreProcessor(object):
    PREPROCESS = []
    # Fix Baen markup
    BAEN = [ 
                     (re.compile(r'page-break-before:\s*\w+([\s;\}])', re.IGNORECASE), 
                      lambda match: match.group(1)),
                     (re.compile(r'<p>\s*(<a id.*?>\s*</a>)\s*</p>', re.IGNORECASE), 
                      lambda match: match.group(1)),
                     (re.compile(r'<\s*a\s+id="p[0-9]+"\s+name="p[0-9]+"\s*>\s*</a>', re.IGNORECASE), 
                      lambda match: ''),
                     ]
    # Fix pdftohtml markup
    PDFTOHTML  = [
                  # Remove <hr> tags
                  (re.compile(r'<hr.*?>', re.IGNORECASE), lambda match: '<span style="page-break-after:always"> </span>'),
                  # Remove page numbers
                  (re.compile(r'\d+<br>', re.IGNORECASE), lambda match: ''),
                  # Remove <br> and replace <br><br> with <p>
                  (re.compile(r'<br.*?>\s*<br.*?>', re.IGNORECASE), lambda match: '<p>'),
                  (re.compile(r'(.*)<br.*?>', re.IGNORECASE), 
                   lambda match: match.group() if re.match('<', match.group(1).lstrip()) or len(match.group(1)) < 40 
                                else match.group(1)),
                  # Remove hyphenation
                  (re.compile(r'-\n\r?'), lambda match: ''),
                  
                  ]
    
    # Fix Book Designer markup
    BOOK_DESIGNER = [
                     # HR
                     (re.compile('<hr>', re.IGNORECASE),
                      lambda match : '<span style="page-break-after:always"> </span>'),
                     # Create header tags
                     (re.compile('<h2[^><]*?id=BookTitle[^><]*?(align=)*(?(1)(\w+))*[^><]*?>[^><]*?</h2>', re.IGNORECASE),
                      lambda match : '<h1 id="BookTitle" align="%s">%s</h1>'%(match.group(2) if match.group(2) else 'center', match.group(3))),
                     (re.compile('<h2[^><]*?id=BookAuthor[^><]*?(align=)*(?(1)(\w+))*[^><]*?>[^><]*?</h2>', re.IGNORECASE),
                      lambda match : '<h2 id="BookAuthor" align="%s">%s</h2>'%(match.group(2) if match.group(2) else 'center', match.group(3))),
                     (re.compile('<span[^><]*?id=title[^><]*?>(.*?)</span>', re.IGNORECASE|re.DOTALL),
                      lambda match : '<h2 class="title">%s</h2>'%(match.group(1),)),
                     (re.compile('<span[^><]*?id=subtitle[^><]*?>(.*?)</span>', re.IGNORECASE|re.DOTALL),
                      lambda match : '<h3 class="subtitle">%s</h3>'%(match.group(1),)),
                     ]
    
    def is_baen(self, src):
        return re.compile(r'<meta\s+name="Publisher"\s+content=".*?Baen.*?"', 
                          re.IGNORECASE).search(src) is not None
                          
    def is_book_designer(self, raw):
        return re.search('<H2[^><]*id=BookTitle', raw) is not None
    
    def is_pdftohtml(self, src):
        return src.startswith('<!-- created by calibre\'s pdftohtml -->')
                          
    def preprocess(self, html):
        if self.is_baen(html):
            rules = self.BAEN
        elif self.is_book_designer(html):
            rules = self.BOOK_DESIGNER
        elif self.is_pdftohtml(html):
            rules = self.PDFTOHTML
        else:
            rules = []
        for rule in self.PREPROCESS + rules:
            html = rule[0].sub(rule[1], html)
        
        return html    
    
