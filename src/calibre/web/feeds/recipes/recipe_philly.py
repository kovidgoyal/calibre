#!/usr/bin/env  python
__license__   = 'GPL v3'
'''
philly.com/inquirer/
'''
import re
from calibre.web.feeds.recipes import BasicNewsRecipe

class Philly(BasicNewsRecipe):

    title       = 'Philadelphia Inquirer'
    __author__  = 'RadikalDissent'
    language = 'en'
    description = 'Daily news from the Philadelphia Inquirer'
    no_stylesheets        = True
    use_embedded_content  = False
    oldest_article = 1
    max_articles_per_feed = 25
    extra_css = '''
        .byline {font-size: small; color: grey; font-style:italic; }
        .lastline {font-size: small; color: grey; font-style:italic;}
        .contact {font-size: small; color: grey;}
        .contact p {font-size: small; color: grey;}
                '''
    preprocess_regexps = [(re.compile(i[0], re.IGNORECASE | re.DOTALL), i[1]) for i in
       [
        (r'<body.*<h1>', lambda match: '<body><h1>'),
        (r'<font size="2" face="Arial">', lambda match: '<div class="contact"><font class="contact">'),
        (r'<font face="Arial" size="2">', lambda match: '<div class="contact"><font class="contact">')
        ]
    ]
    keep_only_tags = [
        dict(name='h1'),
        dict(name='p', attrs={'class':['byline','lastline']}),
        dict(name='div', attrs={'class':'body-content'}),
    ]

    remove_tags = [
        dict(name='hr'),
        dict(name='p', attrs={'class':'buzzBadge'}),
    ]
    def print_version(self, url):
        return url + '?viewAll=y'


    feeds = [
        ('Front Page', 'http://www.philly.com/inquirer_front_page.rss'),
        ('Business', 'http://www.philly.com/inq_business.rss'),
        ('News', 'http://www.philly.com/inquirer/news/index.rss'),
        ('Nation', 'http://www.philly.com/inq_news_world_us.rss'),
        ('Local', 'http://www.philly.com/inquirer_local.rss'),
        ('Health', 'http://www.philly.com/inquirer_health_science.rss'),
        ('Education', 'http://www.philly.com/inquirer_education.rss'),
        ('Editorial and opinion', 'http://www.philly.com/inq_news_editorial.rss'),
        ('Sports', 'http://www.philly.com/inquirer_sports.rss')
        ]
