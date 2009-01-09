#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
pescanik.net
'''

import string,re
from calibre.web.feeds.news import BasicNewsRecipe

class Pescanik(BasicNewsRecipe):
    title                 = 'Pescanik'
    __author__            = 'Darko Miletic'
    description           = 'Pescanik'
    oldest_article        = 7
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    html2lrf_options = ['--base-font-size', '10']
    html2epub_options = 'base_font_size = "10pt"'
    
    cover_url = "http://pescanik.net/templates/ja_teline/images/logo.png"
    
    preprocess_regexps = [(re.compile(u'\u0110'), lambda match: u'\u00D0')]
    
    remove_tags_after = dict(name='div', attrs={'class':'article_seperator'})
    
    remove_tags = [dict(name='td'  , attrs={'class':'buttonheading'})]

    feeds       = [(u'Pescanik Online', u'http://pescanik.net/index.php?option=com_rd_rss&id=12')]

    def print_version(self, url):
        nurl = url.replace('http://pescanik.net/index.php','http://pescanik.net/index2.php')        
        return nurl + '&pop=1&page=0'
