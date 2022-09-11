#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2022, Kovid Goyal <kovid at kovidgoyal.net>

import json
import re
from xml.sax.saxutils import escape, quoteattr

from calibre.utils.iso8601 import parse_iso8601


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
    lines.append('<div style="text-align: center"><img src={}/>'.format(quoteattr(img)))
    lines.extend(caption_lines)
    lines.append('</div>')


def json_to_html(raw):
    data = json.loads(raw.replace(':undefined', ':null'))
    # open('/t/raw.json', 'w').write(json.dumps(data, indent=2))
    data = data['initialData']['data']
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


def extract_html(soup):
    script = soup.findAll('script', text=lambda x: x and 'window.__preloadedData' in x)[0]
    script = type(u'')(script)
    raw = script[script.find('{'):script.rfind(';')].strip().rstrip(';')
    return json_to_html(raw)
