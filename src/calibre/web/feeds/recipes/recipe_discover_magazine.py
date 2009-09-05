#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
doscovermagazine.com
'''

from calibre.web.feeds.news import BasicNewsRecipe

class DiscoverMagazine(BasicNewsRecipe):
    title = u'Discover Magazine'
    description = u'Science, Technology and the Future' 
    __author__ = 'Mike Diaz' 
    oldest_article = 33
    language = 'en'
 
    max_articles_per_feed = 20 
    feeds = [
             (u'Technology', u'http://discovermagazine.com/topics/technology/rss.xml'), 
             (u'Health - Medicine', u'http://discovermagazine.com/topics/health-medicine/rss.xml'), 
             (u'Mind Brain', u'http://discovermagazine.com/topics/mind-brain/rss.xml'), 
             (u'Space', u'http://discovermagazine.com/topics/space/rss.xml'), 
             (u'Human Origins', u'http://discovermagazine.com/topics/human-origins/rss.xml'), 
             (u'Living World', u'http://discovermagazine.com/topics/living-world/rss.xml'), 
             (u'Environment', u'http://discovermagazine.com/topics/environment/rss.xml'), 
             (u'Physics & Math', u'http://discovermagazine.com/topics/physics-math/rss.xml'), 
             (u'Vital Signs', u'http://discovermagazine.com/columns/vital-signs/rss.xml'), 
             (u"20 Things you didn't know about...", u'http://discovermagazine.com/columns/20-things-you-didnt-know/rss.xml'), 
             (u'Fuzzy Math', u'http://discovermagazine.com/columns/fuzzy-math/rss.xml'), 
             (u'The Brain', u'http://discovermagazine.com/columns/the-brain/rss.xml'), 
             (u'Stupid Science Word of the Month', u'http://discovermagazine.com/columns/stupid-science-word-of-the-month/rss.xml'), 
             (u'Science Not Fiction', u'http://blogs.discovermagazine.com/sciencenotfiction/wp-rss.php')
            ]