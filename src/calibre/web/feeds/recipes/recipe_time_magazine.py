#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
time.com
'''

from calibre.web.feeds.news import BasicNewsRecipe

class Time(BasicNewsRecipe):
    title                 = u'Time'
    __author__            = 'Kovid Goyal'
    description           = 'Weekly magazine'    
    oldest_article        = 7
    max_articles_per_feed = 100
    encoding = 'utf-8'
    no_stylesheets        = True
    language = _('English')
    use_embedded_content  = False
    
    keep_only_tags = [dict(name='div', attrs={'class':'tout1'})]
    remove_tags_after = [dict(id='connectStory')]
    remove_tags    = [
                      dict(name='ul', attrs={'class':['button', 'find']}),
                      dict(name='div', attrs={'class':['nav', 'header', 'sectheader', 
                                                       'searchWrap', 'subNav', 
                                                       'artTools', 'connect',
                                                       'similarrecs']}),
                      dict(name='div', id=['articleSideBar', 'connectStory']),
                      dict(name='dl', id=['links']),                                 
                      ]

    feeds          = [
                       (u'Top Stories', u'http://feedproxy.google.com/time/topstories')
                       ,(u'Nation', u'http://feedproxy.google.com/time/nation')
                       ,(u'Business & Tech', u'http://feedproxy.google.com/time/business')
                       ,(u'Science & Tech', u'http://feedproxy.google.com/time/scienceandhealth')
                       ,(u'World', u'http://feedproxy.google.com/time/world')
                       ,(u'Entertainment', u'http://feedproxy.google.com/time/entertainment')
                       ,(u'Politics', u'http://feedproxy.google.com/time/politics')
                       ,(u'Travel', u'http://feedproxy.google.com/time/travel')
                     ]
    
    def get_article_url(self, article):
        return article.get('guid',  article['link'])
    
    def get_cover_url(self):
        soup = self.index_to_soup('http://www.time.com/time/')
        img = soup.find('img', alt='Current Time.com Cover', width='107')
        if img is not None:
            return img.get('src', None)
        
    def print_version(self, url):
        try:
            soup = self.index_to_soup(url)
            print_link = soup.find('a', {'id':'prt'})
            return 'http://www.time.com' + print_link['href']
        except:
            self.log_exception('Failed to find print version for '+url)
        return ''
