#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import absolute_import, division, print_function, unicode_literals

import json

from calibre.web.feeds.news import BasicNewsRecipe
from calibre import prepare_string_for_xml as escape
from calibre.utils.iso8601 import parse_iso8601


def classes(classes):
    q = frozenset(classes.split(' '))
    return dict(attrs={
        'class': lambda x: x and frozenset(x.split()).intersection(q)})


def extract_json(raw):
    s = raw.find("window['__natgeo__']")
    script = raw[s:raw.find('</script>', s)]
    return json.loads(script[script.find('{'):].rstrip(';'))['page']['content']['prismarticle']


def parse_contributors(grp):
    for item in grp:
        line = '<div class="auth">' + escape(item['title']) + ' '
        for c in item['contributors']:
            line += escape(c['displayName'])
        yield line + '</div>'


def parse_lead_image(media):
    if 'image' in media:
        yield '<p>'
        if 'dsc' in media['image']:
            yield '<div><img src="{}" alt="{}"></div>'.format(
                escape(media['image']['src'], True), escape(media['image']['dsc'], True))
        else:
            yield '<div><img src="{}"></div>'.format(escape(media['image']['src'], True))
        if 'caption' in media and 'credit' in media:
            yield '<div class="cap">' + media['caption'] + '<span class="cred"> ' + media['credit'] + '</span></div>'
        elif 'caption' in media:
            yield '<div class="cap">' + media['caption'] + '</div>'
        yield '</p>'


def parse_inline(inl):
    if inl.get('content', {}).get('name', '') == 'Image':
        props = inl['content']['props']
        yield '<p>'
        if 'image' in props:
            yield '<div class="img"><img src="{}"></div>'.format(props['image']['src'])
        if 'caption' in props:
            yield '<div class="cap">{}<span class="cred">{}</span></div>'.format(
                props['caption']['text'], ' ' + props['caption']['credit']
            )
        yield '</p>'
    if inl.get('content', {}).get('name', '') == 'ImageGroup':
        if 'images' in inl['content']['props']:
            for imgs in inl['content']['props']['images']:
                yield '<p>'
                if 'src' in imgs:
                    yield '<div class="img"><img src="{}"></div>'.format(imgs['src'])
                if 'caption' in imgs:
                    yield '<div class="cap">{}<span class="cred">{}</span></div>'.format(
                        imgs['caption']['text'], ' ' + imgs['caption']['credit']
                    )
                yield '</p>'


def parse_cont(content):
    for cont in content.get('content', {}):
        if isinstance(cont, dict):
            yield from parse_body(cont)
        if isinstance(cont, str):
            yield cont


def parse_body(x):
    if isinstance(x, dict):
        if 'type' in x:
            tag = x['type']
            if tag == 'inline':
                yield ''.join(parse_inline(x))
            elif 'attrs' in x and 'href' in x.get('attrs', ''):
                yield '<' + tag + ' href = "{}">'.format(x['attrs']['href'])
                for yld in parse_cont(x):
                    yield yld
                yield '</' + tag + '>'
            else:
                yield '<' + tag + '>'
                for yld in parse_cont(x):
                    yield yld
                yield '</' + tag + '>'
    elif isinstance(x, list):
        for y in x:
            if isinstance(y, dict):
                yield from parse_body(y)


def parse_article(edg):
    sc = edg['schma']
    yield '<div class="sub">' + escape(edg['sctn']) + '</div>'
    yield '<h1>' + escape(sc['sclTtl']) + '</h1>'
    yield '<div class="byline">' + escape(sc['sclDsc']) + '</div>'
    yield '<p>'
    for line in parse_contributors(edg['cntrbGrp']):
        yield line
    ts = parse_iso8601(edg['mdDt'], as_utc=False).strftime('%B %d, %Y')
    yield '<div class="time">Published: ' + escape(ts) + '</div>'
    if 'readTime' in edg:
        yield '<div class="time">' + escape(edg['readTime']) + '</div>'
    yield '</p>'
    if edg.get('ldMda', {}).get('cmsType') == 'image':
        for line in parse_lead_image(edg['ldMda']):
            yield line
    for main in edg['prismData']['mainComponents']:
        if main['name'] == 'Body':
            for item in main['props']['body']:
                if isinstance(item, dict):
                    if item.get('type', '') == 'inline':
                        for inl in parse_inline(item):
                            yield inl
                elif isinstance(item, list):
                    for line in item:
                        yield ''.join(parse_body(line))


def article_parse(data):
    yield "<html><body>"
    for frm in data['frms']:
        if not frm:
            continue
        for mod in frm.get('mods', ()):
            for edg in mod.get('edgs', ()):
                if edg.get('cmsType') == 'ImmersiveLeadTile':
                    if 'image' in edg.get('cmsImage', {}):
                        for line in parse_lead_image(edg['cmsImage']):
                            yield line
                if edg.get('cmsType') == 'ArticleBodyTile':
                    for line in parse_article(edg):
                        yield line
    yield "</body></html>"


class NatGeo(BasicNewsRecipe):
    title = u'National Geographic History'
    description = (
        'From Caesar to Napoleon, the Pyramids to the Parthenon, the Trojan War to the Civil War—National Geographic '
        'HISTORY draws readers in with more than 5,000 years of people, places, and things to explore.'
    )
    language = 'en'
    encoding = 'utf8'
    publisher = 'nationalgeographic.com'
    category = 'science, nat geo'
    __author__ = 'Kovid Goyal, unkn0wn'
    description = 'Inspiring people to care about the planet since 1888'
    timefmt = ' [%a, %d %b, %Y]'
    no_stylesheets = True
    use_embedded_content = False
    remove_attributes = ['style']
    remove_javascript = False
    masthead_url = 'https://i.natgeofe.com/n/e76f5368-6797-4794-b7f6-8d757c79ea5c/ng-logo-2fl.png?w=600&h=600'
    resolve_internal_links = True

    extra_css = '''
        blockquote { color:#404040; }
        .byline, i { font-style:italic; color:#202020; }
        .cap { font-size:small; }
        img {display:block; margin:0 auto;}
        .cred { font-style:italic; font-size:small; color:#404040; }
        .auth, .time, .sub { font-size:small; color:#5c5c5c; }
    '''

    def get_cover_url(self):
        soup = self.index_to_soup('https://ngsingleissues.nationalgeographic.com/history')
        wrap = soup.find(attrs={'class':'product-image-wrapper'})
        return wrap.img['src']

    def parse_index(self):
        soup = self.index_to_soup('https://www.nationalgeographic.com/history/history-magazine')
        ans = []
        for article in soup.findAll('article'):
            a = article.find('a')
            url = a['href']
            if url.startswith('/'):
                url = 'https://www.nationalgeographic.com' + url
            title = self.tag_to_string(article.find(**classes('PromoTile__Title--truncated')))
            ans.append({'title': title, 'url': url})
            self.log(title, '  ', url)
        return [('Articles', ans)]

    def preprocess_raw_html(self, raw_html, url):
        data = extract_json(raw_html)
        return '\n'.join(article_parse(data))

    def preprocess_html(self, soup):
        for h2 in soup.findAll('h2'):
            h2.name = 'h4'
        for img in soup.findAll('img', src=True):
            # for high res images use '?w=2000&h=2000'
            img['src'] = img['src'] + '?w=600&h=600'
        return soup

    def populate_article_metadata(self, article, soup, first):
        summ = soup.find(attrs={'class':'byline'})
        if summ:
            article.summary = self.tag_to_string(summ)
            article.text_summary = self.tag_to_string(summ)
