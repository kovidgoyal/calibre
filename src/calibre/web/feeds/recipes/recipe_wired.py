#!/usr/bin/env  python
__license__   = 'GPL v3'
__docformat__ = 'restructuredtext en'


from calibre.web.feeds.news import BasicNewsRecipe

class Wired(BasicNewsRecipe):

    title = 'Wired.com'
    __author__ = 'Kovid Goyal'
    description = 'Technology news'
    timefmt  = ' [%Y%b%d  %H%M]'
    language = 'en'

    no_stylesheets = True

    remove_tags_before = dict(name='div', id='content')
    remove_tags = [dict(id=['social_tools', 'outerWrapper', 'sidebar',
        'footer', 'advertisement', 'blog_subscription_unit',
        'brightcove_component']),
        {'class':'entryActions'},
        dict(name=['noscript', 'script'])]

    feeds = [
        ('Top News', 'http://feeds.wired.com/wired/index'),
        ('Culture', 'http://feeds.wired.com/wired/culture'),
        ('Software', 'http://feeds.wired.com/wired/software'),
        ('Mac', 'http://feeds.feedburner.com/cultofmac/bFow'),
        ('Gadgets', 'http://feeds.wired.com/wired/gadgets'),
        ('Cars', 'http://feeds.wired.com/wired/cars'),
        ('Entertainment', 'http://feeds.wired.com/wired/entertainment'),
        ('Gaming', 'http://feeds.wired.com/wired/gaming'),
        ('Science', 'http://feeds.wired.com/wired/science'),
        ('Med Tech', 'http://feeds.wired.com/wired/medtech'),
        ('Politics', 'http://feeds.wired.com/wired/politics'),
        ('Tech Biz', 'http://feeds.wired.com/wired/techbiz'),
        ('Commentary', 'http://feeds.wired.com/wired/commentary'),
        ]

    def print_version(self, url):
        return url.replace('http://www.wired.com/', 'http://www.wired.com/print/')


