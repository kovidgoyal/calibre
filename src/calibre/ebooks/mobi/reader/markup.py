#!/usr/bin/env python
# License: GPLv3 Copyright: 2012, Kovid Goyal <kovid@kovidgoyal.net>

import os
import re

from calibre.ebooks.chardet import strip_encoding_declarations


def resource_href(resource_map: list[str | None], num: int) -> str | None:
    # Resource numbers in kindle:embed URLs are 1-based
    if 0 < num <= len(resource_map):
        return resource_map[num - 1]
    return None


def update_internal_links(mobi8_reader, log):
    # need to update all links that are internal which
    # are based on positions within the xhtml files **BEFORE**
    # cutting and pasting any pieces into the xhtml text files

    #   kindle:pos:fid:XXXX:off:YYYYYYYYYY  (used for internal link within xhtml)
    #       XXXX is the offset in records into divtbl
    #       YYYYYYYYYYYY is a base32 number you add to the divtbl insertpos to get final position

    mr = mobi8_reader

    # pos:fid pattern
    posfid_pattern = re.compile(rb'''(<a.*?href=.*?>)''', re.IGNORECASE)
    posfid_index_pattern = re.compile(rb'''['"]kindle:pos:fid:([0-9A-V]+):off:([0-9A-V]+).*?["']''')

    parts = []
    for part in mr.parts:
        srcpieces = posfid_pattern.split(part)
        for j in range(1, len(srcpieces), 2):
            tag = srcpieces[j]
            if tag.startswith(b'<'):
                for m in posfid_index_pattern.finditer(tag):
                    posfid = m.group(1)
                    offset = m.group(2)
                    try:
                        filename, idtag = mr.get_id_tag_by_pos_fid(int(posfid, 32), int(offset, 32))
                    except ValueError:
                        log.warn('Invalid link, points to nowhere, ignoring')
                        replacement = b'#'
                    else:
                        suffix = (b'#' + idtag) if idtag else b''
                        replacement = filename.split('/')[-1].encode(mr.header.codec) + suffix
                        replacement = replacement.replace(b'"', b'&quot;')
                    tag = posfid_index_pattern.sub(b'"' + replacement + b'"', tag, 1)
                srcpieces[j] = tag
        raw = b''.join(srcpieces)
        try:
            parts.append(raw.decode(mr.header.codec))
        except UnicodeDecodeError:
            log.warn('Failed to decode text in KF8 part, replacing bad bytes')
            parts.append(raw.decode(mr.header.codec, 'replace'))

    # All parts are now unicode and have no internal links
    return parts


def remove_kindlegen_markup(parts, aid_anchor_suffix, linked_aids):

    # we can safely remove all of the Kindlegen generated aid attributes and
    # calibre generated cid attributes
    find_tag_with_aid_pattern = re.compile(r'''(<[^>]*\s[ac]id\s*=[^>]*>)''', re.IGNORECASE)
    within_tag_aid_position_pattern = re.compile(r'''\s[ac]id\s*=['"]([^'"]*)['"]''')

    for i in range(len(parts)):
        part = parts[i]
        srcpieces = find_tag_with_aid_pattern.split(part)
        for j in range(len(srcpieces)):
            tag = srcpieces[j]
            if tag.startswith('<'):
                for m in within_tag_aid_position_pattern.finditer(tag):
                    try:
                        aid = m.group(1)
                    except IndexError:
                        aid = None
                    replacement = ''
                    if aid in linked_aids:
                        assert isinstance(aid, str)
                        replacement = f' id="{aid + "-" + aid_anchor_suffix}"'
                    tag = within_tag_aid_position_pattern.sub(replacement, tag, 1)
                srcpieces[j] = tag
        part = ''.join(srcpieces)
        parts[i] = part

    # we can safely remove all of the Kindlegen generated data-AmznPageBreak
    # attributes
    find_tag_with_AmznPageBreak_pattern = re.compile(r'''(<[^>]*\sdata-AmznPageBreak=[^>]*>)''', re.IGNORECASE)
    within_tag_AmznPageBreak_position_pattern = re.compile(r'''\sdata-AmznPageBreak=['"]([^'"]*)['"]''')

    for i in range(len(parts)):
        part = parts[i]
        srcpieces = find_tag_with_AmznPageBreak_pattern.split(part)
        for j in range(len(srcpieces)):
            tag = srcpieces[j]
            if tag.startswith('<'):
                srcpieces[j] = within_tag_AmznPageBreak_position_pattern.sub(lambda m: f' style="page-break-after:{m.group(1)}"', tag)
        part = ''.join(srcpieces)
        parts[i] = part


def update_flow_links(mobi8_reader, resource_map, log):
    #   kindle:embed:XXXX?mime=image/gif (png, jpeg, etc) (used for images)
    #   kindle:flow:XXXX?mime=YYYY/ZZZ (used for style sheets, svg images, etc)
    #   kindle:embed:XXXX   (used for fonts)

    mr = mobi8_reader
    flows = []

    img_pattern = re.compile(r'''(<[img\s|image\s|svg:image\s][^>]*>)''', re.IGNORECASE)
    img_index_pattern = re.compile(r'''['"]kindle:embed:([0-9A-V]+)[^'"]*['"]''', re.IGNORECASE)

    tag_pattern = re.compile(r'''(<[^>]*>)''')
    flow_pattern = re.compile(r'''['"]kindle:flow:([0-9A-V]+)\?mime=([^'"]+)['"]''', re.IGNORECASE)

    # Both quoted and unquoted forms, the quote character is preserved so that
    # url() tokens inside style attributes remain valid
    url_pattern = re.compile(r'''url\(\s*(?:"(kindle:[^"]*)"|'(kindle:[^']*)'|(kindle:[^'"()\s]*))\s*\)''', re.IGNORECASE)
    kindle_url_pattern = re.compile(r'''kindle:(embed|flow):([0-9A-V]+)(?:\?(.*))?''', re.IGNORECASE | re.DOTALL)

    def rewrite_url(m: re.Match[str]) -> str:
        if m.group(1) is not None:
            quote, url = '"', m.group(1)
        elif m.group(2) is not None:
            quote, url = "'", m.group(2)
        else:
            quote, url = '', m.group(3)
        km = kindle_url_pattern.fullmatch(url)
        if km is None:
            log.warn(f'Ignoring unrecognized Kindle URL: {m.group()}')
            return m.group()
        kind, num = km.group(1).lower(), int(km.group(2), 32)
        if kind == 'embed':
            href = resource_href(resource_map, num)
            if not href:
                rtype = 'image' if 'mime=image/' in (km.group(3) or '').lower() else 'font'
                log.warn(f'Referenced {rtype} {num} was not recognized as a valid {rtype} in {m.group()}')
                return m.group()
            return f'url({quote}../{href}{quote})'
        try:
            fi = mr.flowinfo[num]
        except IndexError:
            fi = None
        if fi is None or fi.format != 'file':
            log.warn(f'Ignoring invalid flow reference in: {m.group()}')
            return m.group()
        return f'url({quote}../{fi.dir}/{fi.fname}{quote})'

    def flow_as_unicode(flow):
        if isinstance(flow, bytes):
            try:
                flow = flow.decode(mr.header.codec)
            except UnicodeDecodeError:
                log.error(f'Flow part has invalid {mr.header.codec} encoded bytes')
                flow = flow.decode(mr.header.codec, 'replace')
        return flow

    for flow in mr.flows:
        if flow is None:  # 0th flow is None
            flows.append(flow)
            continue
        flow = flow_as_unicode(flow)

        # links to raster image files from image tags
        # image_pattern
        srcpieces = img_pattern.split(flow)

        for j in range(1, len(srcpieces), 2):
            tag = srcpieces[j]
            if tag.startswith(('<im', '<svg:image')):
                for m in img_index_pattern.finditer(tag):
                    num = int(m.group(1), 32)
                    href = resource_href(resource_map, num)
                    if href:
                        replacement = f'"{"../" + href}"'
                        tag = img_index_pattern.sub(replacement, tag, 1)
                    else:
                        log.warn(f'Referenced image {num} was not recognized as a valid image in {tag}')
                srcpieces[j] = tag
        flow = ''.join(srcpieces)

        # replacements inside css url(): images, fonts and other flows
        flow = url_pattern.sub(rewrite_url, flow)

        # flow pattern not inside url()
        srcpieces = re.split(tag_pattern, flow)
        for j in range(1, len(srcpieces), 2):
            tag = srcpieces[j]
            if tag.startswith('<'):
                for m in re.finditer(flow_pattern, tag):
                    try:
                        num = int(m.group(1), 32)
                        fi = mr.flowinfo[num]
                    except IndexError:
                        log.warn('Ignoring invalid flow reference in tag', tag)
                        tag = ''
                    else:
                        if fi.format == 'inline':
                            flowtext = flow_as_unicode(mr.flows[num])
                            tag = flowtext
                        else:
                            replacement = '"../' + fi.dir + '/' + fi.fname + '"'
                            tag = flow_pattern.sub(replacement, tag, 1)
                srcpieces[j] = tag
        flow = ''.join(srcpieces)

        flows.append(flow)

    # All flows are now unicode and have links resolved
    return flows


def insert_flows_into_markup(parts, flows, mobi8_reader, log):
    mr = mobi8_reader

    # kindle:flow:XXXX?mime=YYYY/ZZZ (used for style sheets, svg images, etc)
    tag_pattern = re.compile(r'''(<[^>]*>)''')
    flow_pattern = re.compile(r'''['"]kindle:flow:([0-9A-V]+)\?mime=([^'"]+)['"]''', re.IGNORECASE)
    for i in range(len(parts)):
        part = parts[i]

        # flow pattern
        srcpieces = tag_pattern.split(part)
        for j in range(1, len(srcpieces), 2):
            tag = srcpieces[j]
            if tag.startswith('<'):
                for m in flow_pattern.finditer(tag):
                    num = int(m.group(1), 32)
                    try:
                        fi = mr.flowinfo[num]
                    except IndexError:
                        log.warn(f'Ignoring invalid flow reference: {m.group()}')
                        tag = ''
                    else:
                        if fi.format == 'inline':
                            tag = flows[num]
                        else:
                            replacement = '"../' + fi.dir + '/' + fi.fname + '"'
                            tag = flow_pattern.sub(replacement, tag, 1)
                srcpieces[j] = tag
        part = ''.join(srcpieces)
        # store away modified version
        parts[i] = part


def insert_images_into_markup(parts, resource_map, log):
    # Handle any embedded raster images links in the xhtml text
    # kindle:embed:XXXX?mime=image/gif (png, jpeg, etc) (used for images)
    img_pattern = re.compile(r'''(<[img\s|image\s][^>]*>)''', re.IGNORECASE)
    img_index_pattern = re.compile(r'''[('"]kindle:embed:([0-9A-V]+)[^')"]*[)'"]''')

    style_pattern = re.compile(r'''(<[a-zA-Z0-9]+\s[^>]*style\s*=\s*[^>]*>)''', re.IGNORECASE)

    for i in range(len(parts)):
        part = parts[i]
        srcpieces = img_pattern.split(part)
        for j in range(1, len(srcpieces), 2):
            tag = srcpieces[j]
            if tag.startswith('<im'):
                for m in img_index_pattern.finditer(tag):
                    num = int(m.group(1), 32)
                    href = resource_href(resource_map, num)
                    if href:
                        replacement = f'"{"../" + href}"'
                        tag = img_index_pattern.sub(replacement, tag, 1)
                    else:
                        log.warn(f'Referenced image {num} was not recognized as a valid image in {tag}')
                srcpieces[j] = tag
        part = ''.join(srcpieces)
        # store away modified version
        parts[i] = part

    # Replace urls used in style attributes
    for i in range(len(parts)):
        part = parts[i]
        srcpieces = style_pattern.split(part)
        for j in range(1, len(srcpieces), 2):
            tag = srcpieces[j]
            if 'kindle:embed' in tag:
                for m in img_index_pattern.finditer(tag):
                    num = int(m.group(1), 32)
                    href = resource_href(resource_map, num)
                    osep = m.group()[0]
                    csep = m.group()[-1]
                    if href:
                        replacement = '{}{}{}'.format(osep, '../' + href, csep)
                        tag = img_index_pattern.sub(replacement, tag, 1)
                    else:
                        log.warn(f'Referenced image {num} was not recognized as a valid image in {tag}')
                srcpieces[j] = tag
        part = ''.join(srcpieces)
        # store away modified version
        parts[i] = part


def upshift_markup(parts):
    tag_pattern = re.compile(r'''(<(?:svg)[^>]*>)''', re.IGNORECASE)

    for i in range(len(parts)):
        part = parts[i]

        # tag pattern
        srcpieces = re.split(tag_pattern, part)
        for j in range(1, len(srcpieces), 2):
            tag = srcpieces[j]
            if tag[:4].lower() == '<svg':
                tag = tag.replace('preserveaspectratio', 'preserveAspectRatio')
                tag = tag.replace('viewbox', 'viewBox')
            srcpieces[j] = tag
        part = ''.join(srcpieces)
        # store away modified version
        parts[i] = part


def expand_mobi8_markup(mobi8_reader, resource_map, log):
    # First update all internal links that are based on offsets
    parts = update_internal_links(mobi8_reader, log)

    # Remove pointless markup inserted by kindlegen
    remove_kindlegen_markup(parts, mobi8_reader.aid_anchor_suffix.decode('utf-8'), mobi8_reader.linked_aids)

    # Handle substitutions for the flows pieces first as they may
    # be inlined into the xhtml text
    flows = update_flow_links(mobi8_reader, resource_map, log)

    # Insert inline flows into the markup
    insert_flows_into_markup(parts, flows, mobi8_reader, log)

    # Insert raster images into markup
    insert_images_into_markup(parts, resource_map, log)

    # Perform general markup cleanups
    upshift_markup(parts)

    # Update the parts and flows stored in the reader
    mobi8_reader.parts = parts
    mobi8_reader.flows = flows

    # write out the parts and file flows
    os.mkdir('text')  # directory containing all parts
    spine = []
    for i, part in enumerate(parts):
        pi = mobi8_reader.partinfo[i]
        with open(os.path.join(pi.type, pi.filename), 'wb') as f:
            part = strip_encoding_declarations(part)
            part = part.replace('<head>', '<head><meta charset="UTF-8"/>', 1)
            f.write(part.encode('utf-8'))
            spine.append(f.name)

    for i, flow in enumerate(flows):
        fi = mobi8_reader.flowinfo[i]
        if fi.format == 'file':
            if not os.path.exists(fi.dir):
                os.mkdir(fi.dir)
            with open(os.path.join(fi.dir, fi.fname), 'wb') as f:
                f.write(flow.encode('utf-8'))

    return spine


def find_tests():
    import unittest
    from types import SimpleNamespace

    from calibre.ebooks.mobi.reader.mobi8 import FlowInfo

    class RecordingLog:
        def __init__(self) -> None:
            self.warnings: list[str] = []

        def warn(self, *args: object) -> None:
            self.warnings.append(' '.join(map(str, args)))

        def error(self, *args: object) -> None:
            self.warnings.append(' '.join(map(str, args)))

    class TestFlowLinks(unittest.TestCase):
        resource_map = ['images/00001.jpeg', 'fonts/00002.ttf', None]
        flowinfo = [
            FlowInfo(None, None, None, None),
            FlowInfo('css', 'file', 'styles', '0001.css'),
            FlowInfo('css', 'file', 'styles', '0002.css'),
            FlowInfo('css', 'inline', None, None),
        ]

        def convert(self, css: str) -> tuple[str, list[str]]:
            reader = SimpleNamespace(flows=[None, css], flowinfo=self.flowinfo, header=SimpleNamespace(codec='utf-8'))
            log = RecordingLog()
            flows = update_flow_links(reader, self.resource_map, log)
            return flows[1], log.warnings

        def assert_converts(self, src: str, expected: str) -> None:
            output, warnings = self.convert(src)
            self.assertEqual(output, expected)
            self.assertEqual(warnings, [])

        def test_quoting_is_preserved(self):
            for url, expected in (
                ('kindle:embed:0002?mime=application/x-font-ttf', '../fonts/00002.ttf'),
                ('kindle:embed:0002', '../fonts/00002.ttf'),
                ('kindle:embed:0001?mime=image/jpeg', '../images/00001.jpeg'),
                ('kindle:flow:0002?mime=text/css', '../styles/0002.css'),
            ):
                for q in ('', '"', "'"):
                    with self.subTest(url=url, quote=q):
                        self.assert_converts(f'a {{ b: url({q}{url}{q}); }}', f'a {{ b: url({q}{expected}{q}); }}')
            self.assert_converts('@import url( "kindle:flow:0001?mime=text/css" );', '@import url("../styles/0001.css");')

        def test_multiple_urls(self):
            self.assert_converts(
                '@font-face { src: url(kindle:embed:0002?mime=font/ttf) format("truetype"), url("kindle:embed:0002") }'
                ' p { background: url(KINDLE:EMBED:0001?mime=image/jpeg) }',
                '@font-face { src: url(../fonts/00002.ttf) format("truetype"), url("../fonts/00002.ttf") } p { background: url(../images/00001.jpeg) }',
            )

        def test_extra_query_parameters(self):
            self.assert_converts('url(kindle:embed:0002?foo=1&mime=font/ttf)', 'url(../fonts/00002.ttf)')

        def test_style_attribute_is_not_broken(self):
            self.assert_converts(
                '<div style="background: url(kindle:embed:0001?mime=image/jpeg)"/>',
                '<div style="background: url(../images/00001.jpeg)"/>',
            )

        def test_invalid_references_are_preserved_with_warning(self):
            for url, expected_warning in (
                ('url("kindle:embed:0003?mime=font/ttf")', 'Referenced font 3'),
                ('url(kindle:embed:0003?mime=image/png)', 'Referenced image 3'),
                ('url(kindle:embed:0000)', 'Referenced font 0'),
                ('url(kindle:embed:00ZZ)', 'unrecognized'),
                ('url(kindle:embed:00|1)', 'unrecognized'),
                ('url(kindle:embed:0100)', 'Referenced font 1024'),
                ('url(kindle:flow:0003?mime=text/css)', 'invalid flow'),
                ('url(kindle:flow:0000?mime=text/css)', 'invalid flow'),
                ('url(kindle:flow:0100?mime=text/css)', 'invalid flow'),
            ):
                with self.subTest(url=url):
                    output, warnings = self.convert(url)
                    self.assertEqual(output, url)
                    self.assertEqual(len(warnings), 1, warnings)
                    self.assertIn(expected_warning, warnings[0])

        def test_non_kindle_urls_untouched(self):
            self.assert_converts('url(images/x.png) url("kindle.png")', 'url(images/x.png) url("kindle.png")')

    class TestImageLinks(unittest.TestCase):
        def test_out_of_range_image_references(self):
            parts = ['<img src="kindle:embed:0000?mime=image/jpeg"/><p style="background: url(kindle:embed:0005)"/>']
            log = RecordingLog()
            insert_images_into_markup(parts, ['images/00001.jpeg'], log)
            self.assertIn('kindle:embed:0000', parts[0])
            self.assertIn('kindle:embed:0005', parts[0])
            self.assertEqual(len(log.warnings), 2, log.warnings)

    ans = unittest.defaultTestLoader.loadTestsFromTestCase(TestFlowLinks)
    ans.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(TestImageLinks))
    return ans
