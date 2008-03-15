#!/usr/bin/env  python

##    Copyright (C) 2008 Kovid Goyal kovid@kovidgoyal.net
##    This program is free software; you can redistribute it and/or modify
##    it under the terms of the GNU General Public License as published by
##    the Free Software Foundation; either version 2 of the License, or
##    (at your option) any later version.
##
##    This program is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##    GNU General Public License for more details.
##
##    You should have received a copy of the GNU General Public License along
##    with this program; if not, write to the Free Software Foundation, Inc.,
##    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

from genshi.template import MarkupTemplate

class Template(MarkupTemplate):
    
    STYLE = '''\
            .article_date {
                font-size: x-small; color: gray; font-family: monospace;
            }
            
            .article_description {
                font-size: small; font-family: sans; text-indent: 0pt;
            }
            
            a.article {
                font-weight: bold; font-size: large;
            }
            
            a.feed {
                font-weight: bold; font-size: large;
            }
'''
    
    def generate(self, *args, **kwargs):
        if not kwargs.has_key('style'):
            kwargs['style'] = self.STYLE
        return MarkupTemplate.generate(self, *args, **kwargs)
    
class NavBarTemplate(Template):
    
    def __init__(self):
        Template.__init__(self, '''\
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" 
    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" 
      xml:lang="en"
      xmlns:xi="http://www.w3.org/2001/XInclude"
      xmlns:py="http://genshi.edgewall.org/" 
       
>
    <body>
        <div class="navbar" style="text-align:center">
            <hr py:if="bottom" />
            <py:if test="art != num - 1">
            | <a href="../article_${str(art+1)}/index.html">Next</a>
            </py:if>
            | <a href="../index.html#article_${str(art)}">Up one level</a> 
            <py:if test="two_levels">
            | <a href="../../index.html#_${str(feed)}">Up two levels</a>
            </py:if>
            <py:if test="art != 0">
            | <a href="../article_${str(art-1)}/index.html">Previous</a>
            </py:if>
            |
            <hr py:if="not bottom" />
        </div>
    </body>
</html>
''')

    def generate(self, bottom, feed, art, number_of_articles_in_feed, two_levels):
        return Template.generate(self, bottom=bottom, art=art, num=number_of_articles_in_feed, two_levels=two_levels)
    

class IndexTemplate(Template):
    
    def __init__(self):
        Template.__init__(self, '''\
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" 
    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" 
      xml:lang="en"
      xmlns:xi="http://www.w3.org/2001/XInclude"
      xmlns:py="http://genshi.edgewall.org/" 
       
>
    <head>
        <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
        <title>${title}</title>
        <style type="text/css">
            ${style}
        </style>
    </head>
    <body>
        <h1>${title}</h1>
        <?python
        from datetime import datetime
        ?>
        <p style="text-align:right">${datetime.now().strftime(str(datefmt))}</p>
        <ul>
            <py:for each="i, feed in enumerate(feeds)">
            <li py:if="feed" id="feed_${str(i)}">
                <a class="feed" href="${'feed_%d/index.html'%i}">${feed.title}</a>
            </li>
            </py:for>
        </ul>
    </body>
</html>
''')

    def generate(self, title, datefmt, feeds):
        return Template.generate(self, title=title, datefmt=datefmt, feeds=feeds)
    
    
class FeedTemplate(Template):
    
    def __init__(self):
        Template.__init__(self, '''\
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" 
    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" 
      xml:lang="en"
      xmlns:xi="http://www.w3.org/2001/XInclude"
      xmlns:py="http://genshi.edgewall.org/" 
       
>
    <head>
        <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
        <title>${feed.title}</title>
        <style type="text/css">
            ${style}
        </style>
    </head>
    <body style="page-break-before:always">
        <h2>${feed.title}</h2>
        <py:if test="feed.image">
        <div class="feed_image">
            <img alt="${feed.image_alt}" src="${feed.image_url}" />
        </div>
        </py:if>
        <div py:if="feed.description">
            ${feed.description}
        </div>
        <ul>
            <py:for each="i, article in enumerate(feed.articles)">
            <li id="${'article_%d'%i}" py:if="getattr(article, 'downloaded', False)">
                <a class="article" href="${article.url}">${article.title}</a>
                <span class="article_date">${article.localtime.strftime(" [%a, %d %b %H:%M]")}</span>
                <p class="article_decription" py:if="article.summary">
                    ${Markup(article.summary)}
                </p>
            </li>
            </py:for>
        </ul>
    </body>
</html>
''')
        
    def generate(self, feed):
        return Template.generate(self, feed=feed)
