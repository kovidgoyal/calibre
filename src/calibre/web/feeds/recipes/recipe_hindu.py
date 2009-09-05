from __future__ import with_statement
__license__ = 'GPL 3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'

import re
from calibre.web.feeds.news import BasicNewsRecipe

class TheHindu(BasicNewsRecipe):
    title                 = u'The Hindu'
    language = 'en'

    oldest_article        = 7
    __author__            = _('Kovid Goyal')
    max_articles_per_feed = 100
    
    remove_tags_before = {'name':'font', 'class':'storyhead'}
    preprocess_regexps = [
                (re.compile(r'<!-- story ends -->.*', re.DOTALL), 
                 lambda match: '</body></html>'),                                                    
                          ]
    
    feeds          = [
      (u'Main - Font Page', u'http://www.hindu.com/rss/01hdline.xml'), 
      (u'Main - National', u'http://www.hindu.com/rss/02hdline.xml'), 
      (u'Main - International', u'http://www.hindu.com/rss/03hdline.xml'), 
      (u'Main - Opinion', u'http://www.hindu.com/rss/05hdline.xml'), 
      (u'Main - Business', u'http://www.hindu.com/rss/06hdline.xml'), 
      (u'Main - Sport', u'http://www.hindu.com/rss/07hdline.xml'), 
      (u'Main - Weather / Religion / Crossword / Cartoon', 
       u'http://www.hindu.com/rss/10hdline.xml'), 
      (u'Main - Engagements', u'http://www.hindu.com/rss/26hdline.xml'), 
      (u'Supplement - Literary Review', 
       u'http://www.hindu.com/rss/lrhdline.xml'), 
      (u'Supplement - Sunday Magazine', 
       u'http://www.hindu.com/rss/maghdline.xml'), 
      (u'Supplement - Open Page', u'http://www.hindu.com/rss/ophdline.xml'), 
      (u'Supplement - Business Review', 
       u'http://www.hindu.com/rss/bizhdline.xml'), 
      (u'Supplement - Book Review', 
       u'http://www.hindu.com/rss/brhdline.xml'), 
      (u'Supplement - Science & Technology', 
       u'http://www.hindu.com/rss/setahdline.xml')
      ]
    
    def postprocess_html(self, soup, first_fetch):
        for t in soup.findAll(['table', 'tr', 'td']):
            t.name = 'div'
        return soup