#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2022, Kovid Goyal <kovid at kovidgoyal.net>

import json
import re
import sys
from pprint import pprint
from xml.sax.saxutils import escape, quoteattr

from calibre.utils.iso8601 import parse_iso8601

module_version = 4  # needed for live updates
pprint


def is_heading(tn):
    return tn in ('Heading1Block', 'Heading2Block', 'Heading3Block', 'Heading4Block')


def process_inline_text(lines, block):
    text = ''
    if 'text@stripHtml' in block:
        text = escape(block['text@stripHtml'])
    elif 'renderedRepresentation' in block:  # happens in byline blocks
        text = block['renderedRepresentation']
    elif 'text' in block:
        text = block['text']
    if text:
        for fmt in block.get('formats', ()):
            tn = fmt['__typename']
            if tn == 'LinkFormat':
                ab = fmt
                text = '<a href="{}" title="{}">{}</a>'.format(ab['url'], ab.get('title') or '', text)
            elif tn == 'BoldFormat':
                text = '<b>' + text + '</b>'
        lines.append(text)


def process_paragraph(lines, block, content_key='content'):
    tn = block['__typename']
    m = re.match(r'Heading([1-6])Block', tn)
    if m is not None:
        tag = 'h' + m.group(1)
    else:
        tag = 'p'
    ta = block.get('textAlign') or 'LEFT'
    style = 'text-align: {}'.format(ta.lower())
    lines.append('<{} style="{}">'.format(tag, style))
    for item in block[content_key]:
        tn = item['__typename']
        if tn in ('TextInline', 'Byline'):
            process_inline_text(lines, item)
    lines.append('</' + tag + '>')


def process_timestamp(lines, block):
    ts = block['timestamp']
    dt = parse_iso8601(ts, as_utc=False)
    lines.append('<p class="timestamp">' + escape(dt.strftime('%b %d, %Y')) + '</p>')


def process_header(lines, block):
    label = block.get('label')
    if label:
        process_paragraph(lines, label)
    headline = block.get('headline')
    if headline:
        process_paragraph(lines, headline)
    summary = block.get('summary')
    if summary:
        process_paragraph(lines, summary)
    lm = block.get('ledeMedia')
    if lm and lm.get('__typename') == 'ImageBlock':
        process_image_block(lines, lm)
    byline = block.get('byline')
    if byline:
        process_paragraph(lines, byline, content_key='bylines')
    timestamp = block.get('timestampBlock')
    if timestamp:
        process_timestamp(lines, timestamp)


def process_image_block(lines, block):
    media = block['media']
    caption = media.get('caption')
    caption_lines = []
    if caption:
        process_inline_text(caption_lines, caption)
    crops = media['crops']
    renditions = crops[0]['renditions']
    img = renditions[0]['url']
    if 'web.archive.org' in img:
        img = img.partition('/')[-1]
        img = img[img.find('https://'):]
    lines.append('<div style="text-align: center"><div style="text-align: center"><img src={}/></div><div style="font-size: smaller">'.format(quoteattr(img)))
    lines.extend(caption_lines)
    lines.append('</div></div>')


def json_to_html(raw):
    data = json.loads(raw.replace(':undefined', ':null'))
    # open('/t/raw.json', 'w').write(json.dumps(data, indent=2))
    try:
        data = data['initialData']['data']
    except TypeError:
        data = data['initialState']
        return live_json_to_html(data)
    article = next(iter(data.values()))
    body = article['sprinkledBody']['content']
    lines = []
    for item in body:
        tn = item['__typename']
        if tn in ('HeaderBasicBlock', 'HeaderLegacyBlock', 'HeaderFullBleedVerticalBlock'):
            process_header(lines, item)
        elif tn in ('ParagraphBlock', 'LabelBlock', 'DetailBlock') or is_heading(tn):
            process_paragraph(lines, item)
        elif tn == 'ImageBlock':
            process_image_block(lines, item)
    return '<html><body>' + '\n'.join(lines) + '</body></html>'


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
    script = type(u'')(script)
    raw = script[script.find('{'):script.rfind(';')].strip().rstrip(';')
    return json_to_html(raw)


def download_url(url=None, br=None):
    # Get the URL from the Wayback machine
    from mechanize import Request
    host = 'http://localhost:8090'
    host = 'https://wayback1.calibre-ebook.com'
    if url is None:
        url = sys.argv[-1]
    rq = Request(
        host + '/nytimes',
        data=json.dumps({"url": url}),
        headers={'User-Agent': 'calibre', 'Content-Type': 'application/json'}
    )
    if br is None:
        from calibre import browser
        br = browser()
    br.set_handle_gzip(True)
    return br.open_novisit(rq, timeout=3 * 60).read()


if __name__ == '__main__':
    f = sys.argv[-1]
    raw = open(f).read()
    if f.endswith('.html'):
        from calibre.ebooks.BeautifulSoup import BeautifulSoup
        soup = BeautifulSoup(raw)
        print(extract_html(soup))
    else:
        print(json_to_html(raw))
