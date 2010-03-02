#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
from calibre.utils.genshi.template import MarkupTemplate
from calibre import preferred_encoding, strftime


class Template(MarkupTemplate):

    def generate(self, *args, **kwargs):
        if not kwargs.has_key('style'):
            kwargs['style'] = ''
        for key in kwargs.keys():
            if isinstance(kwargs[key], basestring) and not isinstance(kwargs[key], unicode):
                kwargs[key] = unicode(kwargs[key], 'utf-8', 'replace')
        for arg in args:
            if isinstance(arg, basestring) and not isinstance(arg, unicode):
                arg = unicode(arg, 'utf-8', 'replace')

        return MarkupTemplate.generate(self, *args, **kwargs)

class NavBarTemplate(Template):

    def __init__(self):
        Template.__init__(self, u'''\
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml"
      xml:lang="en"
      xmlns:xi="http://www.w3.org/2001/XInclude"
      xmlns:py="http://genshi.edgewall.org/"

>
    <head>
        <style py:if="extra_css" type="text/css">
        ${extra_css}
        </style>
    </head>
    <body>
        <div class="calibre_navbar calibre_rescale_70" style="text-align:${'center' if center else 'left'};">
            <hr py:if="bottom" />
            <p py:if="bottom" style="text-align:left">
                This article was downloaded by <b>${__appname__}</b> from <a href="${url}">${url}</a>
            </p>
            <br py:if="bottom" /><br py:if="bottom" />
            <py:if test="art != num - 1 and not bottom">
            | <a href="${prefix}../article_${str(art+1)}/index.html">Next</a>
            </py:if>
            <py:if test="art == num - 1 and not bottom">
            | <a href="${prefix}../../feed_${str(feed+1)}/index.html">Next</a>
            </py:if>
            | <a href="${prefix}../index.html#article_${str(art)}">Section menu</a>
            <py:if test="two_levels">
            | <a href="${prefix}../../index.html#feed_${str(feed)}">Main menu</a>
            </py:if>
            <py:if test="art != 0 and not bottom">
            | <a href="${prefix}../article_${str(art-1)}/index.html">Previous</a>
            </py:if>
            |
            <hr py:if="not bottom" />
        </div>
    </body>
</html>
''')

    def generate(self, bottom, feed, art, number_of_articles_in_feed,
                 two_levels, url, __appname__, prefix='', center=True,
                 extra_css=None):
        if prefix and not prefix.endswith('/'):
            prefix += '/'
        return Template.generate(self, bottom=bottom, art=art, feed=feed,
                                 num=number_of_articles_in_feed,
                                 two_levels=two_levels, url=url,
                                 __appname__=__appname__, prefix=prefix,
                                 center=center, extra_css=extra_css)


class IndexTemplate(Template):

    def __init__(self):
        Template.__init__(self, u'''\
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
        <style py:if="style" type="text/css">
            ${style}
        </style>
        <style py:if="extra_css" type="text/css">
            ${extra_css}
        </style>
    </head>
    <body>
        <div class="calibre_rescale_100">
            <h1 class="calibre_recipe_title calibre_rescale_180">${title}</h1>
            <p style="text-align:right">${date}</p>
            <ul class="calibre_feed_list">
                <py:for each="i, feed in enumerate(feeds)">
                <li py:if="feed" id="feed_${str(i)}">
                    <a class="feed calibre_rescale_120" href="${'feed_%d/index.html'%i}">${feed.title}</a>
                </li>
                </py:for>
            </ul>
        </div>
    </body>
</html>
''')

    def generate(self, title, datefmt, feeds, extra_css=None):
        if isinstance(datefmt, unicode):
            datefmt = datefmt.encode(preferred_encoding)
        date = strftime(datefmt)
        return Template.generate(self, title=title, date=date, feeds=feeds,
                                 extra_css=extra_css)


class FeedTemplate(Template):

    def __init__(self):
        Template.__init__(self, u'''\
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
        <style py:if="style" type="text/css">
            ${style}
        </style>
        <style py:if="extra_css" type="text/css">
            ${extra_css}
        </style>
    </head>
    <body style="page-break-before:always">
    <div class="calibre_rescale_100">
        <h2 class="calibre_feed_title calibre_rescale_160">${feed.title}</h2>
        <py:if test="getattr(feed, 'image', None)">
        <div class="calibre_feed_image">
            <img alt="${feed.image_alt}" src="${feed.image_url}" />
        </div>
        </py:if>
        <div class="calibre_feed_description calibre_rescale_80" py:if="getattr(feed, 'description', None)">
            ${feed.description}<br />
        </div>
        <ul class="calibre_article_list">
            <py:for each="i, article in enumerate(feed.articles)">
            <li id="${'article_%d'%i}" py:if="getattr(article, 'downloaded',
            False)" style="padding-bottom:0.5em" class="calibre_rescale_100">
                <a class="article calibre_rescale_120" href="${article.url}">${article.title}</a>
                <span class="article_date">${article.localtime.strftime(" [%a, %d %b %H:%M]")}</span>
                <div class="article_description calibre_rescale_70" py:if="article.summary">
                    ${Markup(cutoff(article.text_summary))}
                </div>
            </li>
            </py:for>
        </ul>
        <div class="calibre_navbar calibre_rescale_70">
            | <a href="../index.html">Up one level</a> |
        </div>
        </div>
    </body>
</html>
''')

    def generate(self, feed, cutoff, extra_css=None):
        return Template.generate(self, feed=feed, cutoff=cutoff,
                                 extra_css=extra_css)

class EmbeddedContent(Template):

    def __init__(self):
        Template.__init__(self, u'''\
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml"
      xml:lang="en"
      xmlns:xi="http://www.w3.org/2001/XInclude"
      xmlns:py="http://genshi.edgewall.org/"

>
    <head>
        <title>${article.title}</title>
    </head>

    <body>
        <h2>${article.title}</h2>
        <div>
            ${Markup(article.content if len(article.content if article.content else '') > len(article.summary if article.summary else '') else article.summary)}
        </div>
    </body>
</html>
''')

    def generate(self, article):
        return Template.generate(self, article=article)
