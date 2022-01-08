#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

from collections import defaultdict
from uuid import uuid4

from calibre.ebooks.oeb.base import OEB_STYLES
from calibre.ebooks.oeb.transforms.subset import find_font_face_rules


def obfuscate_font_data(data, key):
    prefix = bytearray(data[:32])
    key = bytearray(reversed(key.bytes))
    prefix = bytes(bytearray(prefix[i]^key[i % len(key)] for i in range(len(prefix))))
    return prefix + data[32:]


class FontsManager:

    def __init__(self, namespace, oeb, opts):
        self.namespace = namespace
        self.oeb, self.log, self.opts = oeb, oeb.log, opts

    def serialize(self, text_styles, fonts, embed_relationships, font_data_map):
        makeelement = self.namespace.makeelement
        font_families, seen = set(), set()
        for ts in text_styles:
            if ts.font_family:
                lf = ts.font_family.lower()
                if lf not in seen:
                    seen.add(lf)
                    font_families.add(ts.font_family)
        family_map = {}
        for family in sorted(font_families):
            family_map[family] = makeelement(fonts, 'w:font', w_name=family)

        embedded_fonts = []
        for item in self.oeb.manifest:
            if item.media_type in OEB_STYLES and hasattr(item.data, 'cssRules'):
                embedded_fonts.extend(find_font_face_rules(item, self.oeb))

        num = 0
        face_map = defaultdict(set)
        rel_map = {}
        for ef in embedded_fonts:
            ff = ef['font-family'][0]
            if ff not in font_families:
                continue
            num += 1
            bold = ef['weight'] > 400
            italic = ef['font-style'] != 'normal'
            tag = 'Regular'
            if bold or italic:
                tag = 'Italic'
                if bold and italic:
                    tag = 'BoldItalic'
                elif bold:
                    tag = 'Bold'
            if tag in face_map[ff]:
                continue
            face_map[ff].add(tag)
            font = family_map[ff]
            key = uuid4()
            item = ef['item']
            rid = rel_map.get(item)
            if rid is None:
                rel_map[item] = rid = 'rId%d' % num
                fname = 'fonts/font%d.odttf' % num
                makeelement(embed_relationships, 'Relationship', Id=rid, Type=self.namespace.names['EMBEDDED_FONT'], Target=fname)
                font_data_map['word/' + fname] = obfuscate_font_data(item.data, key)
            makeelement(font, 'w:embed' + tag, r_id=rid,
                        w_fontKey='{%s}' % key.urn.rpartition(':')[-1].upper(),
                        w_subsetted="true" if self.opts.subset_embedded_fonts else "false")
