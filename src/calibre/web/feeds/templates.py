#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

from lxml import html, etree
from lxml.html.builder import HTML, HEAD, TITLE, STYLE, DIV, BODY, \
        STRONG, BR, SPAN, A, HR, UL, LI, H2, IMG, P as PT, \
        TABLE, TD, TR

from calibre import preferred_encoding, strftime, isbytestring

def CLASS(*args, **kwargs): # class is a reserved word in Python
    kwargs['class'] = ' '.join(args)
    return kwargs

class Template(object):

    IS_HTML = True

    def generate(self, *args, **kwargs):
        if not kwargs.has_key('style'):
            kwargs['style'] = ''
        for key in kwargs.keys():
            if isbytestring(kwargs[key]):
                kwargs[key] = kwargs[key].decode('utf-8', 'replace')
            if kwargs[key] is None:
                kwargs[key] = u''
        args = list(args)
        for i in range(len(args)):
            if isbytestring(args[i]):
                args[i] = args[i].decode('utf-8', 'replace')
            if args[i] is None:
                args[i] = u''

        self._generate(*args, **kwargs)

        return self

    def render(self, *args, **kwargs):
        if self.IS_HTML:
            return html.tostring(self.root, encoding='utf-8',
                    include_meta_content_type=True, pretty_print=True)
        return etree.tostring(self.root, encoding='utf-8', xml_declaration=True,
                pretty_print=True)

class NavBarTemplate(Template):

    def _generate(self, bottom, feed, art, number_of_articles_in_feed,
                 two_levels, url, __appname__, prefix='', center=True,
                 extra_css=None, style=None):
        head = HEAD(TITLE('navbar'))
        if style:
            head.append(STYLE(style, type='text/css'))
        if extra_css:
            head.append(STYLE(extra_css, type='text/css'))

        if prefix and not prefix.endswith('/'):
            prefix += '/'
        align = 'center' if center else 'left'
        navbar = DIV(CLASS('calibre_navbar', 'calibre_rescale_70',
            style='text-align:'+align))
        if bottom:
            navbar.append(HR())
            text = 'This article was downloaded by '
            p = PT(text, STRONG(__appname__), A(url, href=url), style='text-align:left')
            p[0].tail = ' from '
            navbar.append(p)
            navbar.append(BR())
            navbar.append(BR())
        else:
            next = 'feed_%d'%(feed+1) if art == number_of_articles_in_feed - 1 \
                    else 'article_%d'%(art+1)
            up = '../..' if art == number_of_articles_in_feed - 1 else '..'
            href = '%s%s/%s/index.html'%(prefix, up, next)
            navbar.text = '| '
            navbar.append(A('Next', href=href))
        href = '%s../index.html#article_%d'%(prefix, art)
        navbar.iterchildren(reversed=True).next().tail = ' | '
        navbar.append(A('Section Menu', href=href))
        href = '%s../../index.html#feed_%d'%(prefix, feed)
        navbar.iterchildren(reversed=True).next().tail = ' | '
        navbar.append(A('Main Menu', href=href))
        if art > 0 and not bottom:
            href = '%s../article_%d/index.html'%(prefix, art-1)
            navbar.iterchildren(reversed=True).next().tail = ' | '
            navbar.append(A('Previous', href=href))
        navbar.iterchildren(reversed=True).next().tail = ' | '
        if not bottom:
            navbar.append(HR())

        self.root = HTML(head, BODY(navbar))

class TouchscreenNavBarTemplate(Template):

    def _generate(self, bottom, feed, art, number_of_articles_in_feed,
                 two_levels, url, __appname__, prefix='', center=True,
                 extra_css=None, style=None):
        head = HEAD(TITLE('navbar'))
        if style:
            head.append(STYLE(style, type='text/css'))
        if extra_css:
            head.append(STYLE(extra_css, type='text/css'))

        if prefix and not prefix.endswith('/'):
            prefix += '/'
        align = 'center' if center else 'left'
        navbar = DIV(CLASS('calibre_navbar', 'calibre_rescale_100',
            style='text-align:'+align))
        if bottom:
            navbar.append(DIV(style="border-top:1px solid gray;border-bottom:1em solid white"))
            text = 'This article was downloaded by '
            p = PT(text, STRONG(__appname__), A(url, href=url), style='text-align:left')
            p[0].tail = ' from '
            navbar.append(p)
            navbar.append(BR())
            navbar.append(BR())
        else:
            next = 'feed_%d'%(feed+1) if art == number_of_articles_in_feed - 1 \
                    else 'article_%d'%(art+1)
            up = '../..' if art == number_of_articles_in_feed - 1 else '..'
            href = '%s%s/%s/index.html'%(prefix, up, next)
            navbar.text = '| '
            navbar.append(A('Next', href=href))

        href = '%s../index.html#article_%d'%(prefix, art)
        navbar.iterchildren(reversed=True).next().tail = ' | '
        navbar.append(A('Section Menu', href=href))
        href = '%s../../index.html#feed_%d'%(prefix, feed)
        navbar.iterchildren(reversed=True).next().tail = ' | '
        navbar.append(A('Main Menu', href=href))
        if art > 0 and not bottom:
            href = '%s../article_%d/index.html'%(prefix, art-1)
            navbar.iterchildren(reversed=True).next().tail = ' | '
            navbar.append(A('Previous', href=href))

        navbar.iterchildren(reversed=True).next().tail = ' | '
        if not bottom:
            navbar.append(DIV(style="border-top:1px solid gray;border-bottom:1em solid white"))

        self.root = HTML(head, BODY(navbar))

class IndexTemplate(Template):

    def _generate(self, title, masthead, datefmt, feeds, extra_css=None, style=None):
        if isinstance(datefmt, unicode):
            datefmt = datefmt.encode(preferred_encoding)
        date = strftime(datefmt)
        head = HEAD(TITLE(title))
        if style:
            head.append(STYLE(style, type='text/css'))
        if extra_css:
            head.append(STYLE(extra_css, type='text/css'))
        ul = UL(CLASS('calibre_feed_list'))
        for i, feed in enumerate(feeds):
            if feed:
                li = LI(A(feed.title, CLASS('feed', 'calibre_rescale_120',
                    href='feed_%d/index.html'%i)), id='feed_%d'%i)
                ul.append(li)
        div = DIV(
                PT(IMG(src=masthead,alt="masthead"),style='text-align:center'),
                PT(date, style='text-align:right'),
                ul,
                CLASS('calibre_rescale_100'))
        self.root = HTML(head, BODY(div))

class TouchscreenIndexTemplate(Template):

    def _generate(self, title, masthead, datefmt, feeds, extra_css=None, style=None):
        if isinstance(datefmt, unicode):
            datefmt = datefmt.encode(preferred_encoding)
        date = '%s, %s %s, %s' % (strftime('%A'), strftime('%B'), strftime('%d').lstrip('0'), strftime('%Y'))
        masthead_p = etree.Element("p")
        masthead_p.set("style","text-align:center")
        masthead_img = etree.Element("img")
        masthead_img.set("src",masthead)
        masthead_img.set("alt","masthead")
        masthead_p.append(masthead_img)

        head = HEAD(TITLE(title))
        if style:
            head.append(STYLE(style, type='text/css'))
        if extra_css:
            head.append(STYLE(extra_css, type='text/css'))

        toc = TABLE(CLASS('toc'),width="100%",border="0",cellpadding="3px")
        for i, feed in enumerate(feeds):
            if feed:
                tr = TR()
                tr.append(TD( CLASS('calibre_rescale_120'), A(feed.title, href='feed_%d/index.html'%i)))
                tr.append(TD( '%s' % len(feed.articles), style="text-align:right"))
                toc.append(tr)
        div = DIV(
                masthead_p,
                PT(date, style='text-align:center'),
                #DIV(style="border-color:gray;border-top-style:solid;border-width:thin"),
                DIV(style="border-top:1px solid gray;border-bottom:1em solid white"),
                toc)
        self.root = HTML(head, BODY(div))

class FeedTemplate(Template):

    def _generate(self, feed, cutoff, extra_css=None, style=None):
        head = HEAD(TITLE(feed.title))
        if style:
            head.append(STYLE(style, type='text/css'))
        if extra_css:
            head.append(STYLE(extra_css, type='text/css'))
        body = BODY(style='page-break-before:always')
        div = DIV(
                H2(feed.title,
                    CLASS('calibre_feed_title', 'calibre_rescale_160')),
                CLASS('calibre_rescale_100')
              )
        body.append(div)
        if getattr(feed, 'image', None):
            div.append(DIV(IMG(
                alt = feed.image_alt if feed.image_alt else '',
                src = feed.image_url
                ),
                CLASS('calibre_feed_image')))
        if getattr(feed, 'description', None):
            d = DIV(feed.description, CLASS('calibre_feed_description',
                'calibre_rescale_80'))
            d.append(BR())
            div.append(d)
        ul = UL(CLASS('calibre_article_list'))
        for i, article in enumerate(feed.articles):
            if not getattr(article, 'downloaded', False):
                continue
            li = LI(
                    A(article.title, CLASS('article calibre_rescale_120',
                                    href=article.url)),
                    SPAN(article.formatted_date, CLASS('article_date')),
                    CLASS('calibre_rescale_100', id='article_%d'%i,
                            style='padding-bottom:0.5em')
                    )
            if article.summary:
                li.append(DIV(cutoff(article.text_summary),
                    CLASS('article_description', 'calibre_rescale_70')))
            ul.append(li)
        div.append(ul)
        navbar = DIV('| ', CLASS('calibre_navbar', 'calibre_rescale_70'))
        link = A('Up one level', href="../index.html")
        link.tail = ' |'
        navbar.append(link)
        div.append(navbar)

        self.root = HTML(head, body)

class TouchscreenFeedTemplate(Template):

    def _generate(self, feed, cutoff, extra_css=None, style=None):
        head = HEAD(TITLE(feed.title))
        if style:
            head.append(STYLE(style, type='text/css'))
        if extra_css:
            head.append(STYLE(extra_css, type='text/css'))
        body = BODY(style='page-break-before:always')
        div = DIV(
                H2(feed.title, CLASS('calibre_feed_title', 'calibre_rescale_160')),
                DIV(style="border-top:1px solid gray;border-bottom:1em solid white")
                )
        body.append(div)
        if getattr(feed, 'image', None):
            div.append(DIV(IMG(
                alt = feed.image_alt if feed.image_alt else '',
                src = feed.image_url
                ),
                CLASS('calibre_feed_image')))
        if getattr(feed, 'description', None):
            d = DIV(feed.description, CLASS('calibre_feed_description',
                'calibre_rescale_80'))
            d.append(BR())
            div.append(d)

        toc = TABLE(CLASS('toc'),width="100%",border="0",cellpadding="3px")
        for i, article in enumerate(feed.articles):
            if not getattr(article, 'downloaded', False):
                continue
            tr = TR()

            if True:
                div_td = DIV(
                        A(article.title, CLASS('summary_headline','calibre_rescale_120',
                                        href=article.url)),
                        style="display:inline-block")
                if article.author:
                    div_td.append(DIV(article.author,
                        CLASS('summary_byline', 'calibre_rescale_100')))
                if article.summary:
                    div_td.append(DIV(cutoff(article.text_summary),
                        CLASS('summary_text', 'calibre_rescale_100')))
                tr.append(TD(div_td))
            else:
                td = TD(
                        A(article.title, CLASS('summary_headline','calibre_rescale_120',
                                        href=article.url))
                        )
                if article.author:
                    td.append(DIV(article.author,
                        CLASS('summary_byline', 'calibre_rescale_100')))
                if article.summary:
                    td.append(DIV(cutoff(article.text_summary),
                        CLASS('summary_text', 'calibre_rescale_100')))

                tr.append(td)

            toc.append(tr)
        div.append(toc)

        navbar = DIV('| ', CLASS('calibre_navbar', 'calibre_rescale_100'),style='text-align:center')
        link = A('Up one level', href="../index.html")
        link.tail = ' |'
        navbar.append(link)
        div.append(navbar)

        self.root = HTML(head, body)

class EmbeddedContent(Template):

    def _generate(self, article, style=None, extra_css=None):
        content = article.content if article.content else ''
        summary = article.summary if article.summary else ''
        text = content if len(content) > len(summary) else summary
        head = HEAD(TITLE(article.title))
        if style:
            head.append(STYLE(style, type='text/css'))
        if extra_css:
            head.append(STYLE(extra_css, type='text/css'))

        if isbytestring(text):
            text = text.decode('utf-8', 'replace')
        elements = html.fragments_fromstring(text)
        self.root = HTML(head,
                BODY(H2(article.title), DIV()))
        div = self.root.find('body').find('div')
        if elements and isinstance(elements[0], unicode):
            div.text = elements[0]
            elements = list(elements)[1:]
        for elem in elements:
            elem.getparent().remove(elem)
            div.append(elem)

