#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
arstechnica.com
'''

from calibre.web.feeds.news import BasicNewsRecipe

class ArsTechnica(BasicNewsRecipe):
    title          = 'Ars Technica'
    description    = 'The art of technology'
    oldest_article = 7
    no_stylesheets = True
    __author__     = 'Michael Warner'
    max_articles_per_feed = 100
    extra_css = """
body {
   font: normal 19px/180% Times, serif;
}

h1, h2, h3, h4 {
   font: bold 28px/100% Verdana, Arial, Helvetica, sans-serif;
   margin-top: 19px
}
"""
    remove_tags = [
                   dict(id="Masthead"),
                   dict(id="Banner"),
                   dict(id="Nav"),
                   dict(name='div', attrs={'class':'ContentHeader'}), 
                   dict(name='img'), 
                   dict(name='div', attrs={'class':'Inset RelatedStories'}), 
                   dict(name='div', attrs={'class':'Tags'}), 
                   dict(name='div', attrs={'class':'PostOptions flat'}),
                   dict(name='div', attrs={'class':'ContentFooter'}),
                   dict(id="Sidebar"),
                   dict(id="LatestPosts"),
                   dict(id="Footer")]
    feeds       = [(u'News and Features', u'http://feeds.arstechnica.com/arstechnica/BAaf'),
                   (u'Nobel Intent (Science)', u'http://arstechnica.com/journals/science.rssx'),
                   (u'Infinite Loop (Apple)', u'http://arstechnica.com/journals/apple.rssx'),
                   (u'M-Dollar (Microsoft)', u'http://arstechnica.com/journals/microsoft.rssx'),
                   (u'Open Ended (Linux)', u'http://arstechnica.com/journals/linux.rssx'),
                   (u'Opposable Thumbs (Games)', u'http://arstechnica.com/journals/thumbs.rssx'),
                   (u'Kit (Hardware)', u'http://arstechnica.com/journals/hardware.rssx'),
                   (u'Journals', u'http://arstechnica.com/journals.rssx')]
