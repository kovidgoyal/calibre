#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
elpais.es
'''

from calibre.web.feeds.news import BasicNewsRecipe

class ElPais(BasicNewsRecipe):
    title          = u'EL PAIS'
    language = 'es'

    oldest_article = 7
    max_articles_per_feed = 100

    remove_tags    = [dict(name='div', attrs={'class':'zona_superior'}), dict(name='div', attrs={'class':'limpiar'}), dict(name='div', attrs={'id':'pie'})]
    extra_css      = 'h1 {font: sans-serif large;} \n h2 {font: sans-serif medium;} \n h3 {font: sans-serif small;} \n h4 {font: sans-serif bold small;} \n p{ font:10pt serif}'
    
    feeds          = [(u'Internacional', u'http://www.elpais.es/rss/rss_section.html?anchor=elpporint'), (u'Espana', u'http://www.elpais.es/rss/rss_section.html?anchor=elppornac'), (u'Deportes', u'http://www.elpais.es/rss/rss_section.html?anchor=elppordep'), (u'Economia', u'http://www.elpais.es/rss/rss_section.html?anchor=elpporeco'), (u'Tecnologia', u'http://www.elpais.es/rss/rss_section.html?anchor=elpportec'), (u'Cultura', u'http://www.elpais.es/rss/rss_section.html?anchor=elpporcul'), (u'Gente', u'http://www.elpais.es/rss/rss_section.html?anchor=elpporgen'), (u'Sociedad', u'http://www.elpais.es/rss/rss_section.html?anchor=elpporsoc'), (u'Opinion', u'http://www.elpais.es/rss/rss_section.html?anchor=elpporopi')]

    def print_version(self, url): 
        url = url+'?print=1' 
        return url