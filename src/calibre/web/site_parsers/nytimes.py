#!/usr/bin/env python
# License: GPL v3 Copyright: 2022, Kovid Goyal <kovid at kovidgoyal.net>

import json
import re
import sys
from pprint import pprint
from xml.sax.saxutils import escape, quoteattr

from calibre.utils.iso8601 import parse_iso8601

module_version = 6  # needed for live updates
pprint


def parse_image(i):
    if i.get('crops'):
        yield '<div><img src="{}">'.format(i['crops'][0]['renditions'][0]['url'])
    elif i.get('spanImageCrops'):
        yield '<div><img src="{}">'.format(i['spanImageCrops'][0]['renditions'][0]['url'])
    if i.get('caption'):
        yield '<div class="cap">' + ''.join(parse_types(i['caption']))
        if i.get('credit'):
            yield '<span class="cred"> ' + i['credit'] + '</span>'
        yield '</div>'
    yield '</div>'

def parse_img_grid(g):
    for grd in g.get('gridMedia', {}):
        yield ''.join(parse_image(grd))
    if g.get('caption'):
        yield '<div class="cap">{}'.format(g['caption'])
        if g.get('credit'):
            yield '<span class="cred"> ' + g['credit'] + '</span>'
        yield '</div>'

def parse_vid(v):
    if v.get('promotionalMedia'):
        if v.get('headline'):
            if v.get('url'):
                yield '<div><b><a href="{}">Video</a>: '.format(v['url'])\
                    + v['headline'].get('default', '') + '</b></div>'
            elif v['headline'].get('default'):
                yield '<div><b>' + v['headline']['default'] + '</b></div>'
        yield ''.join(parse_types(v['promotionalMedia']))
        if v.get('promotionalSummary'):
            yield '<div class="cap">' + v['promotionalSummary'] + '</div>'

def parse_emb(e):
    if e.get('html') and 'datawrapper.dwcdn.net' in e.get('html', ''):
        dw = re.search(r'datawrapper.dwcdn.net/(.{5})', e['html']).group(1)
        yield '<div><img src="{}">'.format('https://datawrapper.dwcdn.net/' + dw + '/full.png') + '</div>'
    elif e.get('promotionalMedia'):
        if e.get('headline'):
            yield '<div><b>' + e['headline']['default'] + '</b></div>'
        yield ''.join(parse_types(e['promotionalMedia']))
        if e.get('note'):
            yield '<div class="cap">' + e['note'] + '</div>'

def parse_byline(byl):
    for b in byl.get('bylines', {}):
        yield '<div>' + b['renderedRepresentation'] + '</div>'
    yield '<div><b><i>'
    for rl in byl.get('role', {}):
        if ''.join(parse_cnt(rl)).strip():
            yield ''.join(parse_cnt(rl))
    yield '</i></b></div>'

def iso_date(x):
    dt = parse_iso8601(x, as_utc=False)
    return dt.strftime('%b %d, %Y at %I:%M %p')

def parse_header(h):
    if h.get('label'):
        yield '<div class="lbl">' + ''.join(parse_types(h['label'])) + '</div>'
    if h.get('headline'):
        yield ''.join(parse_types(h['headline']))
    if h.get('summary'):
        yield '<p><i>' +  ''.join(parse_types(h['summary'])) + '</i></p>'
    if h.get('ledeMedia'):
        yield ''.join(parse_types(h['ledeMedia']))
    if h.get('byline'):
        yield ''.join(parse_types(h['byline']))
    if h.get('timestampBlock'):
        yield ''.join(parse_types(h['timestampBlock']))

def parse_fmt_type(fm):
    for f in fm.get('formats', {}):
        if f.get('__typename', '') == 'BoldFormat':
            yield '<strong>'
        if f.get('__typename', '') == 'ItalicFormat':
            yield '<em>'
        if f.get('__typename', '') == 'LinkFormat':
            hrf = f['url']
            yield '<a href="{}">'.format(hrf)
    yield fm['text']
    for f in reversed(fm.get('formats', {})):
        if f.get('__typename', '') == 'BoldFormat':
            yield '</strong>'
        if f.get('__typename', '') == 'ItalicFormat':
            yield '</em>'
        if f.get('__typename', '') == 'LinkFormat':
            yield '</a>'

def parse_cnt(cnt):
    if cnt.get('formats'):
        yield ''.join(parse_fmt_type(cnt))
    elif cnt.get('content'):
        for cnt_ in cnt['content']:
            yield from parse_types(cnt_)
    elif cnt.get('text'):
        yield cnt['text']

def parse_types(x):
    if 'Header' in x.get('__typename', ''):
        yield '\n'.join(parse_header(x))

    elif x.get('__typename', '') == 'Heading1Block':
        yield '<h1>' + ''.join(parse_cnt(x)) + '</h1>'
    elif x.get('__typename', '') in {'Heading2Block', 'Heading3Block', 'Heading4Block'}:
        yield '<h4>' + ''.join(parse_cnt(x)) + '</h4>'

    elif x.get('__typename', '') == 'ParagraphBlock':
        yield '<p>' + ''.join(parse_cnt(x)) + '</p>'

    elif x.get('__typename', '') == 'BylineBlock':
        yield '<div class="byl"><br/>' + ''.join(parse_byline(x)) + '</div>'
    elif x.get('__typename', '') == 'LabelBlock':
        yield '<div class="sc">' + ''.join(parse_cnt(x)) + '</div>'
    elif x.get('__typename', '') == 'BlockquoteBlock':
        yield '<blockquote>' + ''.join(parse_cnt(x)) + '</blockquote>'
    elif x.get('__typename', '') == 'TimestampBlock':
        yield '<div class="time">' + iso_date(x['timestamp']) + '</div>'
    elif x.get('__typename', '') == 'LineBreakInline':
        yield '<br/>'
    elif x.get('__typename', '') == 'RuleBlock':
        yield '<hr/>'

    elif x.get('__typename', '') == 'Image':
        yield ''.join(parse_image(x))
    elif x.get('__typename', '') == 'ImageBlock':
        yield ''.join(parse_image(x['media']))
    elif x.get('__typename', '') == 'GridBlock':
        yield ''.join(parse_img_grid(x))

    elif x.get('__typename', '') == 'VideoBlock':
        yield ''.join(parse_types(x['media']))
    elif x.get('__typename', '') == 'Video':
        yield ''.join(parse_vid(x))

    elif x.get('__typename', '') == 'InteractiveBlock':
        yield ''.join(parse_types(x['media']))
    elif x.get('__typename', '') == 'EmbeddedInteractive':
        yield ''.join(parse_emb(x))

    elif x.get('__typename', '') == 'ListBlock':
        yield '<ul>' + ''.join(parse_cnt(x)) + '</ul>'
    elif x.get('__typename', '') == 'ListItemBlock':
        yield '<li>' + ''.join(parse_cnt(x)) + '</li>'

    elif x.get('__typename', '') == 'CapsuleBlock':
        if x['capsuleContent'].get('body'):
            yield ''.join(parse_cnt(x['capsuleContent']['body']))
    elif x.get('__typename', '') == 'Capsule':
        yield ''.join(parse_cnt(x['body']))

    elif x.get('__typename', '') in {
        'TextInline', 'TextOnlyDocumentBlock', 'DocumentBlock', 'SummaryBlock'
    }:
        yield ''.join(parse_cnt(x))

    elif x.get('__typename'):
        if ''.join(parse_cnt(x)).strip():
            yield '<p><i>' + ''.join(parse_cnt(x)) + '</i></p>'

def article_parse(data):
    yield "<html><body>"
    for d in data:
        yield from parse_types(d)
    yield "</body></html>"


def json_to_html(raw):
    data = json.loads(raw.replace(':undefined', ':null'))
    # open('/t/raw.json', 'w').write(json.dumps(data, indent=2))
    try:
        data = data['initialData']['data']
    except TypeError:
        data = data['initialState']
        return live_json_to_html(data)
    content = data['article']['sprinkledBody']['content']
    return '\n'.join(article_parse(content))


def add_live_item(item, item_type, lines):
    a = lines.append
    if item_type == 'text':
        a('<p>' + item['value'] + '</p>')
    elif item_type == 'list':
        a('<li>' + item['value'] + '</li>')
    elif item_type == 'bulletedList':
        a('<ul>')
        for x in item['value']:
            a('<li>' + x + '</li>')
        a('</ul>')
    elif item_type == 'items':
        for x in item['value']:
            a('<h5>' + x['subtitle'] + '</h5>')
            add_live_item({'value': x['text']}, 'text', lines)
    elif item_type == 'section':
        for item in item['value']:
            add_live_item(item, item['type'], lines)
    elif item_type == '':
        b = item
        if b.get('title'):
            a('<h3>' + b['title'] + '</h3>')
        if b.get('imageUrl'):
            a('<div><img src=' + quoteattr(b['imageUrl']) + '/></div>')
        if b.get('leadIn'):
            a('<p>' + b['leadIn'] + '</p>')
        if 'items' in b:
            add_live_item({'value': b['items']}, 'items', lines)
            return
        if 'bulletedList' in b:
            add_live_item({'value': b['bulletedList']}, 'bulletedList', lines)
            return
        if 'sections' in b:
            for section in b['sections']:
                add_live_item({'value': section['section']}, 'section', lines)
            return
        raise Exception('Unknown item: %s' % b)
    else:
        raise Exception('Unknown item: %s' % b)


def live_json_to_html(data):
    for k, v in data["ROOT_QUERY"].items():
        if isinstance(v, dict) and 'id' in v:
            root = data[v['id']]
    s = data[root['storylines'][0]['id']]
    s = data[s['storyline']['id']]
    title = s['displayName']
    lines = ['<h1>' + escape(title) + '</h1>']
    for b in json.loads(s['experimentalJsonBlob'])['data'][0]['data']:
        b = b['data']
        if isinstance(b, list):
            for x in b:
                add_live_item(x, x['type'], lines)
        else:
            add_live_item(b, '', lines)
    return '<html><body>' + '\n'.join(lines) + '</body></html>'


def extract_html(soup):
    script = soup.findAll('script', text=lambda x: x and 'window.__preloadedData' in x)[0]
    script = str(script)
    raw = script[script.find('{'):script.rfind(';')].strip().rstrip(';')
    return json_to_html(raw)


def download_url_from_wayback(category, url, br=None):
    from mechanize import Request
    host = 'http://localhost:8090'
    host = 'https://wayback1.calibre-ebook.com'
    rq = Request(
        host + '/' + category,
        data=json.dumps({"url": url}),
        headers={'User-Agent': 'calibre', 'Content-Type': 'application/json'}
    )
    if br is None:
        from calibre import browser
        br = browser()
    br.set_handle_gzip(True)
    return br.open_novisit(rq, timeout=3 * 60).read()


def download_url(url=None, br=None):
    # Get the URL from the Wayback machine
    if url is None:
        url = sys.argv[-1]
    return download_url_from_wayback('nytimes', url, br)


if __name__ == '__main__':
    f = sys.argv[-1]
    raw = open(f).read()
    if f.endswith('.html'):
        from calibre.ebooks.BeautifulSoup import BeautifulSoup
        soup = BeautifulSoup(raw)
        print(extract_html(soup))
    else:
        print(json_to_html(raw))
