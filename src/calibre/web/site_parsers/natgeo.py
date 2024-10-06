#!/usr/bin/env python

from __future__ import absolute_import, division, print_function, unicode_literals

import json
from pprint import pprint

from calibre import prepare_string_for_xml as escape
from calibre.utils.iso8601 import parse_iso8601

module_version = 1  # needed for live updates
pprint


def extract_json(raw):
    s = raw.find("window['__natgeo__']")
    script = raw[s : raw.find('</script>', s)]
    return json.loads(script[script.find('{') :].rstrip(';'))['page']['content'][
        'prismarticle'
    ]


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
            yield (
                f'<div><img src="{escape(media["image"]["src"], True)}" '
                f'alt="{escape(media["image"]["dsc"], True)}"></div>'
            )
        else:
            yield f'<div><img src="{escape(media["image"]["src"], True)}"></div>'
        if 'caption' in media and 'credit' in media:
            yield (
                '<div class="cap">'
                + media['caption']
                + '<span class="cred"> '
                + media['credit']
                + '</span></div>'
            )
        elif 'caption' in media:
            yield '<div class="cap">' + media['caption'] + '</div>'
        yield '</p>'


def parse_inline(inl):
    if inl.get('content', {}).get('name', '') == 'Image':
        props = inl['content']['props']
        yield '<p>'
        if 'image' in props:
            yield f'<div class="img"><img src="{props["image"]["src"]}"></div>'
        if 'caption' in props:
            yield (
                f'<div class="cap">{props["caption"].get("text", "")}<span '
                f'class="cred"> {props["caption"].get("credit", "")}</span></div>'
            )
        yield '</p>'
    if inl.get('content', {}).get('name', '') == 'ImageGroup':
        if 'images' in inl['content']['props']:
            for imgs in inl['content']['props']['images']:
                yield '<p>'
                if 'src' in imgs:
                    yield f'<div class="img"><img src="{imgs["src"]}"></div>'
                if 'caption' in imgs:
                    yield (
                        f'<div class="cap">{imgs["caption"].get("text", "")}<span '
                        f'class="cred"> {imgs["caption"].get("credit", "")}</span></div>'
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
                yield '<' + tag + f' href="{x["attrs"]["href"]}">'
                yield from parse_cont(x)
                yield '</' + tag + '>'
            else:
                yield '<' + tag + '>'
                yield from parse_cont(x)
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
    yield from parse_contributors(edg.get('cntrbGrp', {}))
    ts = parse_iso8601(edg['mdDt'], as_utc=False).strftime('%B %d, %Y')
    yield '<div class="time">Published: ' + escape(ts) + '</div>'
    if 'readTime' in edg:
        yield '<div class="time">' + escape(edg['readTime']) + '</div>'
    yield '</p>'
    if edg.get('ldMda', {}).get('cmsType') == 'image':
        yield from parse_lead_image(edg['ldMda'])
    for main in edg['prismData']['mainComponents']:
        if main['name'] == 'Body':
            for item in main['props']['body']:
                if isinstance(item, dict):
                    if item.get('type', '') == 'inline':
                        yield ''.join(parse_inline(item))
                elif isinstance(item, list):
                    for line in item:
                        yield ''.join(parse_body(line))


def article_parse(data):
    yield '<html><body>'
    for frm in data['frms']:
        if not frm:
            continue
        for mod in frm.get('mods', ()):
            for edg in mod.get('edgs', ()):
                if edg.get('cmsType') == 'ImmersiveLeadTile':
                    if 'image' in edg.get('cmsImage', {}):
                        yield from parse_lead_image(edg['cmsImage'])
                if edg.get('cmsType') == 'ArticleBodyTile':
                    yield from parse_article(edg)
    yield '</body></html>'


def extract_html(raw_html):
    data = extract_json(raw_html)
    return '\n'.join(article_parse(data))
