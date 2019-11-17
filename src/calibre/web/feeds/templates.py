#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'


import copy

from lxml import html, etree
from lxml.html.builder import HTML, HEAD, TITLE, STYLE, DIV, BODY, \
        STRONG, BR, SPAN, A, HR, UL, LI, H2, H3, IMG, P as PT, \
        TABLE, TD, TR

from calibre import strftime, isbytestring
from polyglot.builtins import unicode_type


def attrs(*args, **kw):
    rescale = kw.pop('rescale', None)
    if rescale is not None:
        kw['data-calibre-rescale'] = unicode_type(rescale)
    if args:
        kw['class'] = ' '.join(args)
    return kw

# Regular templates


class Template(object):

    IS_HTML = True

    def __init__(self, lang=None):
        self.html_lang = lang

    def generate(self, *args, **kwargs):
        if 'style' not in kwargs:
            kwargs['style'] = ''
        for key in kwargs.keys():
            if isbytestring(kwargs[key]):
                kwargs[key] = kwargs[key].decode('utf-8', 'replace')
            if kwargs[key] is None:
                kwargs[key] = ''
        args = list(args)
        for i in range(len(args)):
            if isbytestring(args[i]):
                args[i] = args[i].decode('utf-8', 'replace')
            if args[i] is None:
                args[i] = ''

        self._generate(*args, **kwargs)

        return self

    def render(self, *args, **kwargs):
        if self.IS_HTML:
            return html.tostring(self.root, encoding='utf-8',
                    include_meta_content_type=True, pretty_print=True)
        return etree.tostring(self.root, encoding='utf-8', xml_declaration=True,
                pretty_print=True)


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
        if elements and isinstance(elements[0], unicode_type):
            div.text = elements[0]
            elements = list(elements)[1:]
        for elem in elements:
            if hasattr(elem, 'getparent'):
                elem.getparent().remove(elem)
            else:
                elem = SPAN(elem)
            div.append(elem)


class IndexTemplate(Template):

    def _generate(self, title, masthead, datefmt, feeds, extra_css=None, style=None):
        self.IS_HTML = False
        date = strftime(datefmt)
        head = HEAD(TITLE(title))
        if style:
            head.append(STYLE(style, type='text/css'))
        if extra_css:
            head.append(STYLE(extra_css, type='text/css'))
        ul = UL(attrs('calibre_feed_list'))
        for i, feed in enumerate(feeds):
            if len(feed):
                li = LI(A(feed.title, attrs('feed', rescale=120,
                    href='feed_%d/index.html'%i)), id='feed_%d'%i)
                ul.append(li)
        div = DIV(
                PT(IMG(src=masthead,alt="masthead"),style='text-align:center'),
                PT(date, style='text-align:right'),
                ul,
                attrs(rescale=100))
        self.root = HTML(head, BODY(div))
        if self.html_lang:
            self.root.set('lang', self.html_lang)


class FeedTemplate(Template):

    def get_navbar(self, f, feeds, top=True):
        if len(feeds) < 2:
            return DIV()
        navbar = DIV('| ', attrs('calibre_navbar', rescale=70,
            style='text-align:center'))
        if not top:
            hr = HR()
            navbar.append(hr)
            navbar.text = None
            hr.tail = '| '

        if f+1 < len(feeds):
            link = A(_('Next section'), href='../feed_%d/index.html'%(f+1))
            link.tail = ' | '
            navbar.append(link)
        link = A(_('Main menu'), href="../index.html")
        link.tail = ' | '
        navbar.append(link)
        if f > 0:
            link = A(_('Previous section'), href='../feed_%d/index.html'%(f-1))
            link.tail = ' |'
            navbar.append(link)
        if top:
            navbar.append(HR())
        return navbar

    def _generate(self, f, feeds, cutoff, extra_css=None, style=None):
        from calibre.utils.cleantext import clean_xml_chars
        feed = feeds[f]
        head = HEAD(TITLE(feed.title))
        if style:
            head.append(STYLE(style, type='text/css'))
        if extra_css:
            head.append(STYLE(extra_css, type='text/css'))
        body = BODY()
        body.append(self.get_navbar(f, feeds))

        div = DIV(
                H2(feed.title,
                    attrs('calibre_feed_title', rescale=160)),
                attrs(rescale=100)
              )
        body.append(div)
        if getattr(feed, 'image', None):
            div.append(DIV(IMG(
                alt=feed.image_alt if feed.image_alt else '',
                src=feed.image_url
                ),
                attrs('calibre_feed_image')))
        if getattr(feed, 'description', None):
            d = DIV(clean_xml_chars(feed.description), attrs('calibre_feed_description', rescale=80))
            d.append(BR())
            div.append(d)
        ul = UL(attrs('calibre_article_list'))
        for i, article in enumerate(feed.articles):
            if not getattr(article, 'downloaded', False):
                continue
            li = LI(
                    A(article.title, attrs('article', rescale=120,
                                    href=article.url)),
                    SPAN(article.formatted_date, attrs('article_date')),
                    attrs(rescale=100, id='article_%d'%i,
                            style='padding-bottom:0.5em')
                    )
            if article.summary:
                li.append(DIV(clean_xml_chars(cutoff(article.text_summary)),
                    attrs('article_description', rescale=70)))
            ul.append(li)
        div.append(ul)
        div.append(self.get_navbar(f, feeds, top=False))
        self.root = HTML(head, body)
        if self.html_lang:
            self.root.set('lang', self.html_lang)


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

        navbar = DIV(attrs('calibre_navbar', rescale=70,
            style='text-align:'+align))
        if bottom:
            if not url.startswith('file://'):
                navbar.append(HR())
                text = 'This article was downloaded by '
                p = PT(text, STRONG(__appname__), A(url, href=url, rel='calibre-downloaded-from'),
                        style='text-align:left; max-width: 100%; overflow: hidden;')
                p[0].tail = ' from '
                navbar.append(p)
                navbar.append(BR())
            navbar.append(BR())
        else:
            next_art = 'feed_%d'%(feed+1) if art == number_of_articles_in_feed - 1 \
                    else 'article_%d'%(art+1)
            up = '../..' if art == number_of_articles_in_feed - 1 else '..'
            href = '%s%s/%s/index.html'%(prefix, up, next_art)
            navbar.text = '| '
            navbar.append(A(_('Next'), href=href))
        href = '%s../index.html#article_%d'%(prefix, art)
        next(navbar.iterchildren(reversed=True)).tail = ' | '
        navbar.append(A(_('Section menu'), href=href))
        href = '%s../../index.html#feed_%d'%(prefix, feed)
        next(navbar.iterchildren(reversed=True)).tail = ' | '
        navbar.append(A(_('Main menu'), href=href))
        if art > 0 and not bottom:
            href = '%s../article_%d/index.html'%(prefix, art-1)
            next(navbar.iterchildren(reversed=True)).tail = ' | '
            navbar.append(A(_('Previous'), href=href))
        next(navbar.iterchildren(reversed=True)).tail = ' | '
        if not bottom:
            navbar.append(HR())

        self.root = HTML(head, BODY(navbar))


# Touchscreen templates
class TouchscreenIndexTemplate(Template):

    def _generate(self, title, masthead, datefmt, feeds, extra_css=None, style=None):
        self.IS_HTML = False
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

        toc = TABLE(attrs('toc'),width="100%",border="0",cellpadding="3px")
        for i, feed in enumerate(feeds):
            if len(feed):
                tr = TR()
                tr.append(TD(attrs(rescale=120), A(feed.title, href='feed_%d/index.html'%i)))
                tr.append(TD('%s' % len(feed.articles), style="text-align:right"))
                toc.append(tr)
        div = DIV(
                masthead_p,
                H3(attrs('publish_date'),date),
                DIV(attrs('divider')),
                toc)
        self.root = HTML(head, BODY(div))
        if self.html_lang:
            self.root.set('lang', self.html_lang)


class TouchscreenFeedTemplate(Template):

    def _generate(self, f, feeds, cutoff, extra_css=None, style=None):
        from calibre.utils.cleantext import clean_xml_chars

        def trim_title(title,clip=18):
            if len(title)>clip:
                tokens = title.split(' ')
                new_title_tokens = []
                new_title_len = 0
                if len(tokens[0]) > clip:
                    return tokens[0][:clip] + '...'
                for token in tokens:
                    if len(token) + new_title_len < clip:
                        new_title_tokens.append(token)
                        new_title_len += len(token)
                    else:
                        new_title_tokens.append('...')
                        title = ' '.join(new_title_tokens)
                        break
            return title

        self.IS_HTML = False
        feed = feeds[f]

        # Construct the navbar
        navbar_t = TABLE(attrs('touchscreen_navbar'))
        navbar_tr = TR()

        # Previous Section
        link = ''
        if f > 0:
            link = A(attrs('feed_link'),
                     trim_title(feeds[f-1].title),
                     href='../feed_%d/index.html' % int(f-1))
        navbar_tr.append(TD(attrs('feed_prev'),link))

        # Up to Sections
        link = A(_('Sections'), href="../index.html")
        navbar_tr.append(TD(attrs('feed_up'),link))

        # Next Section
        link = ''
        if f < len(feeds)-1:
            link = A(attrs('feed_link'),
                     trim_title(feeds[f+1].title),
                     href='../feed_%d/index.html' % int(f+1))
        navbar_tr.append(TD(attrs('feed_next'),link))
        navbar_t.append(navbar_tr)
        top_navbar = navbar_t
        bottom_navbar = copy.copy(navbar_t)
        # print "\n%s\n" % etree.tostring(navbar_t, pretty_print=True)

        # Build the page
        head = HEAD(TITLE(feed.title))
        if style:
            head.append(STYLE(style, type='text/css'))
        if extra_css:
            head.append(STYLE(extra_css, type='text/css'))
        body = BODY()
        div = DIV(
                top_navbar,
                H2(feed.title, attrs('feed_title'))
                )
        body.append(div)

        if getattr(feed, 'image', None):
            div.append(DIV(IMG(
                alt=feed.image_alt if feed.image_alt else '',
                src=feed.image_url
                ),
                attrs('calibre_feed_image')))
        if getattr(feed, 'description', None):
            d = DIV(clean_xml_chars(feed.description), attrs('calibre_feed_description', rescale=80))
            d.append(BR())
            div.append(d)

        for i, article in enumerate(feed.articles):
            if not getattr(article, 'downloaded', False):
                continue

            div_td = DIV(attrs('article_summary'),
                    A(article.title, attrs('summary_headline',rescale=120,
                                    href=article.url)))
            if article.author:
                div_td.append(DIV(article.author,
                    attrs('summary_byline', rescale=100)))
            if article.summary:
                div_td.append(DIV(cutoff(article.text_summary),
                    attrs('summary_text', rescale=100)))
            div.append(div_td)

        div.append(bottom_navbar)
        self.root = HTML(head, body)
        if self.html_lang:
            self.root.set('lang', self.html_lang)


class TouchscreenNavBarTemplate(Template):

    def _generate(self, bottom, feed, art, number_of_articles_in_feed,
                 two_levels, url, __appname__, prefix='', center=True,
                 extra_css=None, style=None):
        head = HEAD(TITLE('navbar'))
        if style:
            head.append(STYLE(style, type='text/css'))
        if extra_css:
            head.append(STYLE(extra_css, type='text/css'))

        navbar = DIV()
        navbar_t = TABLE(attrs('touchscreen_navbar'))
        navbar_tr = TR()

        if bottom and not url.startswith('file://'):
            navbar.append(HR())
            text = 'This article was downloaded by '
            p = PT(text, STRONG(__appname__), A(url, href=url, rel='calibre-downloaded-from'),
                    style='text-align:left; max-width: 100%; overflow: hidden;')
            p[0].tail = ' from '
            navbar.append(p)
            navbar.append(BR())
        # | Previous
        if art > 0:
            link = A(attrs('article_link'),_('Previous'),href='%s../article_%d/index.html'%(prefix, art-1))
            navbar_tr.append(TD(attrs('article_prev'),link))
        else:
            navbar_tr.append(TD(attrs('article_prev'),''))

        # | Articles | Sections |
        link = A(attrs('articles_link'),_('Articles'), href='%s../index.html#article_%d'%(prefix, art))
        navbar_tr.append(TD(attrs('article_articles_list'),link))

        link = A(attrs('sections_link'),_('Sections'), href='%s../../index.html#feed_%d'%(prefix, feed))
        navbar_tr.append(TD(attrs('article_sections_list'),link))

        # | Next
        next_art = 'feed_%d'%(feed+1) if art == number_of_articles_in_feed - 1 \
                else 'article_%d'%(art+1)
        up = '../..' if art == number_of_articles_in_feed - 1 else '..'

        link = A(attrs('article_link'), _('Next'), href='%s%s/%s/index.html'%(prefix, up, next_art))
        navbar_tr.append(TD(attrs('article_next'),link))
        navbar_t.append(navbar_tr)
        navbar.append(navbar_t)
        # print "\n%s\n" % etree.tostring(navbar, pretty_print=True)

        self.root = HTML(head, BODY(navbar))
