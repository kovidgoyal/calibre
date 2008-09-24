#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
sciam.com
'''

from calibre.web.feeds.news import BasicNewsRecipe

class ScientificAmerican(BasicNewsRecipe):
    title = u'Scientific American'
    description = u'Popular science' 
    __author__ = 'Kovid Goyal'
    oldest_article = 30 
    max_articles_per_feed = 100
    use_embedded_content   = False
    remove_tags_before = dict(name='div', attrs={'class':'headline'})
    remove_tags_after  = dict(id='article')
    remove_tags        = [dict(id='sharetools'), dict(id='reddit')]
    html2lrf_options = ['--base-font-size', '8']
    feeds = [
             (u'Latest News', u'http://rss.sciam.com/ScientificAmerican-News'), 
             (u'Global', u'http://rss.sciam.com/ScientificAmerican-Global'), 
             (u'Health', u'http://rss.sciam.com/sciam/health'), 
             (u'Space', u'http://rss.sciam.com/sciam/space'), 
             (u'Technology', u'http://rss.sciam.com/sciam/technology'), 
             (u'Biology', u'http://rss.sciam.com/sciam/biology'), 
             (u'Mind & Brain', u'http://rss.sciam.com/sciam/mind-and-brain'), 
             (u"What's Next", u'http://rss.sciam.com/sciam/whats-next'), 
             (u'Archeology and Paleontology', u'http://www.sciam.com/page.cfm?section=rsscategory&alias=archaeology-and-paleontology'), 
             (u'Physics', u'http://www.sciam.com/page.cfm?section=rsscategory&alias=physics'), 
             (u'Math', u'http://rss.sciam.com/sciam/math'), 
             (u'History of Science', u'http://www.sciam.com/page.cfm?section=rsscategory&alias=history-of-science'), 
             (u'Chemistry', u'http://rss.sciam.com/sciam/chemistry'), 
             (u'Mind Matters', u'http://rss.sciam.com/ScientificAmerican-MindBlog')
            ]
