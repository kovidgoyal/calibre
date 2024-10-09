#!/usr/bin/env python
# License: GPL v3 Copyright: 2022, Kovid Goyal <kovid at kovidgoyal.net>

import json
import re
import sys
from pprint import pprint
from xml.sax.saxutils import escape, quoteattr

from calibre.utils.iso8601 import parse_iso8601

module_version = 10  # needed for live updates
pprint


def parse_image(i):
    crop = i.get('crops') or i.get('spanImageCrops')
    if crop:
        yield f'<div><img src="{crop[0]["renditions"][0]["url"]}" title="{i.get("altText", "")}">'
    if i.get('caption'):
        yield f'<div class="cap">{"".join(parse_types(i["caption"]))}'
        if i.get('credit'):
            yield f'<span class="cred"> {i["credit"]}</span>'
        yield '</div>'
    elif i.get('legacyHtmlCaption'):
        if i['legacyHtmlCaption'].strip():
            yield f'<div class="cap">{i["legacyHtmlCaption"]}</div>'
    yield '</div>'


def parse_img_grid(g):
    for grd in g.get('gridMedia', {}):
        yield ''.join(parse_image(grd))
    if g.get('caption'):
        yield f'<div class="cap">{g["caption"]}'
        if g.get('credit'):
            yield f'<span class="cred"> {g["credit"]}</span>'
        yield '</div>'


def parse_vid(v):
    if v.get('promotionalMedia'):
        headline = v.get('headline', {}).get('default', '')
        rendition = v.get('renditions')
        yield (
            f'<div><b><a href="{rendition[0]["url"]}">Video</a>: {headline}</b></div>'
            if rendition
            else f'<div><b>{headline}</b></div>'
        )
        yield ''.join(parse_types(v['promotionalMedia']))
        if v.get('promotionalSummary'):
            yield f'<div class="cap">{v["promotionalSummary"]}</div>'


def parse_emb(e):
    if e.get('html') and 'datawrapper.dwcdn.net' in e.get('html', ''):
        dw = re.search(r'datawrapper.dwcdn.net/(.{5})', e['html']).group(1)
        yield f'<div><img src="https://datawrapper.dwcdn.net/{dw}/full.png"></div>'
    elif e.get('promotionalMedia'):
        if e.get('headline'):
            yield f'<div><b>{e["headline"]["default"]}</b></div>'
        yield ''.join(parse_types(e['promotionalMedia']))
        if e.get('note'):
            yield f'<div class="cap">{e["note"]}</div>'


def parse_byline(byl):
    for b in byl.get('bylines', {}):
        yield f'<div><b>{b["renderedRepresentation"]}</b></div>'
    yield '<div><i>'
    for rl in byl.get('role', {}):
        if ''.join(parse_cnt(rl)).strip():
            yield ''.join(parse_cnt(rl))
    yield '</i></div>'


def iso_date(x):
    dt = parse_iso8601(x, as_utc=False)
    return dt.strftime('%b %d, %Y at %I:%M %p')


def parse_header(h):
    if h.get('label'):
        yield f'<div class="lbl">{"".join(parse_types(h["label"]))}</div>'
    if h.get('headline'):
        yield ''.join(parse_types(h['headline']))
    if h.get('summary'):
        yield f'<p><i>{"".join(parse_types(h["summary"]))}</i></p>'
    if h.get('ledeMedia'):
        yield ''.join(parse_types(h['ledeMedia']))
    if h.get('byline'):
        yield ''.join(parse_types(h['byline']))
    if h.get('timestampBlock'):
        yield ''.join(parse_types(h['timestampBlock']))


def parse_fmt_type(fm):
    for f in fm.get('formats', {}):
        ftype = f.get('__typename', '')
        if ftype == 'BoldFormat':
            yield '<strong>'
        if ftype == 'ItalicFormat':
            yield '<em>'
        if ftype == 'LinkFormat':
            hrf = f['url']
            yield f'<a href="{hrf}">'
    yield fm.get('text', '')
    for f in reversed(fm.get('formats', {})):
        ftype = f.get('__typename', '')
        if ftype == 'BoldFormat':
            yield '</strong>'
        if ftype == 'ItalicFormat':
            yield '</em>'
        if ftype == 'LinkFormat':
            yield '</a>'


def parse_cnt(cnt):
    for k in cnt:
        if isinstance(cnt[k], list):
            if k == 'formats':
                yield ''.join(parse_fmt_type(cnt))
            else:
                for cnt_ in cnt[k]:
                    yield ''.join(parse_types(cnt_))
        if isinstance(cnt[k], dict):
            yield ''.join(parse_types(cnt[k]))
    if cnt.get('text') and 'formats' not in cnt and 'content' not in cnt:
        if isinstance(cnt['text'], str):
            yield cnt['text']


def parse_types(x):
    typename = x.get('__typename', '')

    align = ''
    if x.get('textAlign'):
        align = f' style="text-align: {x["textAlign"].lower()};"'

    if 'Header' in typename:
        yield '\n'.join(parse_header(x))

    elif typename.startswith('Heading'):
        htag = 'h' + re.match(r'Heading([1-6])Block', typename).group(1)
        yield f'<{htag}{align}>{"".join(parse_cnt(x))}</{htag}>'

    elif typename == 'ParagraphBlock':
        yield f'<p>{"".join(parse_cnt(x))}</p>'
    elif typename in {'DetailBlock', 'TextRunKV'}:
        yield f'<p style="font-size: small;">{"".join(parse_cnt(x))}</p>'

    elif typename == 'BylineBlock':
        yield f'<div class="byl"><br/>{"".join(parse_byline(x))}</div>'
    elif typename == 'LabelBlock':
        yield f'<div class="sc">{"".join(parse_cnt(x))}</div>'
    elif typename == 'BlockquoteBlock':
        yield f'<blockquote>{"".join(parse_cnt(x))}</blockquote>'
    elif typename == 'TimestampBlock':
        yield f'<div class="time">{iso_date(x["timestamp"])}</div>'
    elif typename == 'LineBreakInline':
        yield '<br/>'
    elif typename == 'RuleBlock':
        yield '<hr/>'

    elif typename == 'Image':
        yield ''.join(parse_image(x))

    elif typename == 'GridBlock':
        yield ''.join(parse_img_grid(x))

    elif typename == 'Video':
        yield ''.join(parse_vid(x))

    elif typename == 'EmbeddedInteractive':
        yield ''.join(parse_emb(x))

    elif typename == 'ListBlock':
        yield f'\n<ul>{"".join(parse_cnt(x))}</ul>'
    elif typename == 'ListItemBlock':
        yield f'\n<li>{"".join(parse_cnt(x))}</li>'

    elif typename and typename not in {
        'RelatedLinksBlock',
        'EmailSignupBlock',
        'Dropzone',
    }:
        yield ''.join(parse_cnt(x))


def article_parse(data):
    yield '<html><body>'
    for d in data:
        yield from parse_types(d)
    yield '</body></html>'


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
    for k, v in data['ROOT_QUERY'].items():
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


def extract_html(soup, url):
    if '/interactive/' in url:
        return (
            '<html><body><p><em>'
            + 'This is an interactive article, which is supposed to be read in a browser.'
            + '</p></em></body></html>'
        )
    script = soup.findAll('script', text=lambda x: x and 'window.__preloadedData' in x)[0]
    script = str(script)
    raw = script[script.find('{') : script.rfind(';')].strip().rstrip(';')
    return json_to_html(raw)


def download_url_from_wayback(category, url, br=None):
    from mechanize import Request

    host = 'http://localhost:8090'
    host = 'https://wayback1.calibre-ebook.com'
    rq = Request(
        host + '/' + category,
        data=json.dumps({'url': url}),
        headers={'User-Agent': 'calibre', 'Content-Type': 'application/json'},
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
