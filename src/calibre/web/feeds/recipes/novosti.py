#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
novosti.rs
'''
import locale
from calibre.web.feeds.news import BasicNewsRecipe

class Novosti(BasicNewsRecipe):
    title                 = u'Vecernje Novosti'
    __author__            = u'Darko Miletic'
    description           = u'Vesti'
    oldest_article        = 7
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    timefmt               = ' [%A, %d %B, %Y]' 
#    #Locale setting to get appropriate date/month values in Serbian if possible
#    try:
#      #Windows seting for locale
#      locale.setlocale(locale.LC_TIME,'Serbian (Latin)')
#    except locale.Error:
#      #Linux setting for locale -- choose one appropriate for your distribution
#      try:
#        locale.setlocale(locale.LC_TIME,'sr_YU')
#      except locale.Error:
#        try:
#          locale.setlocale(locale.LC_TIME,'sr_CS@Latn')
#        except locale.Error:
#          try:
#            locale.setlocale(locale.LC_TIME,'sr@Latn')
#          except locale.Error:
#            try:
#              locale.setlocale(locale.LC_TIME,'sr_Latn')
#            except locale.Error:
#              try:
#                locale.setlocale(locale.LC_TIME,'sr_RS')
#              except locale.Error:                  
#                locale.setlocale(locale.LC_TIME,'C')


    keep_only_tags     = [ dict(name='div', attrs={'class':'jednaVest'}) ]
    remove_tags_after  = dict(name='div', attrs={'class':'info_bottom'})
    remove_tags = [
                     dict(name='div', attrs={'class':'info'})
                    ,dict(name='div', attrs={'class':'info_bottom'})
                  ]

    feeds          = [ (u'Vesti', u'http://www.novosti.rs/php/vesti/rss.php')]
