# License: GPLv3 Copyright: 2009, Kovid Goyal <kovid@kovidgoyal.net>

import os
import re
from typing import TYPE_CHECKING

from calibre import CurrentDir
from calibre.customize.conversion import InputFormatPlugin, OptionRecommendation, OutputFormatPlugin

if TYPE_CHECKING:
    from optparse import Values

    from lxml.etree import _Element

    from calibre.ebooks.oeb.base import OEBBook
    from calibre.utils.logging import Log


class OEBOutput(OutputFormatPlugin):
    name = 'OEB Output'
    author = 'Kovid Goyal'
    file_type = 'oeb'
    commit_name = 'oeb_output'

    recommendations = {('pretty_print', True, OptionRecommendation.HIGH)}

    def convert(self, oeb_book: OEBBook, output: str, input_plugin: InputFormatPlugin, opts: Values, log: Log) -> None:
        output_path = output
        from css_parser.css import CSSStyleSheet
        from lxml import etree

        from polyglot.urllib import unquote

        self.log, self.opts = log, opts
        if not os.path.exists(output_path):
            os.makedirs(output_path)
        from calibre.ebooks.oeb.base import NCX_MIME, OEB_STYLES, OPF_MIME, PAGE_MAP_MIME
        from calibre.ebooks.oeb.normalize_css import condense_sheet

        with CurrentDir(output_path):
            results = oeb_book.to_opf2(page_map=True)
            for key in (OPF_MIME, NCX_MIME, PAGE_MAP_MIME):
                href, root = results.pop(key, [None, None])
                if root is not None:
                    if key == OPF_MIME:
                        try:
                            self.workaround_nook_cover_bug(root)
                        except Exception:
                            self.log.exception('Something went wrong while trying to workaround Nook cover bug, ignoring')
                        try:
                            self.workaround_pocketbook_cover_bug(root)
                        except Exception:
                            self.log.exception('Something went wrong while trying to workaround Pocketbook cover bug, ignoring')
                        self.migrate_lang_code(root)
                        self.adjust_mime_types(root)
                    raw = etree.tostring(root, pretty_print=True, encoding='utf-8', xml_declaration=True)
                    if key == OPF_MIME:
                        # Needed as I can't get lxml to output opf:role and
                        # not output <opf:metadata> as well
                        raw = re.sub(rb'(<[/]{0,1})opf:', rb'\1', raw)
                    with open(href, 'wb') as f:  # ty: ignore[no-matching-overload] href is not None when root is not None
                        f.write(raw)

            for item in oeb_book.manifest:
                if (
                    not self.opts.expand_css
                    and item.media_type in OEB_STYLES
                    and isinstance(data := item.data, CSSStyleSheet)
                    and 'nook' not in self.opts.output_profile.short_name
                ):
                    condense_sheet(data)
                path = os.path.abspath(unquote(item.href))
                dir = os.path.dirname(path)
                if not os.path.exists(dir):
                    os.makedirs(dir)
                with open(path, 'wb') as f:
                    f.write(item.bytes_representation)
                item.unload_data_from_memory(memory=path)

    def adjust_mime_types(self, root: _Element) -> None:
        from calibre.ebooks.oeb.polish.utils import adjust_mime_for_epub

        for x in root.xpath('//*[local-name() = "manifest"]/*[local-name() = "item"]'):
            mt = x.get('media-type')
            if mt:
                nmt = adjust_mime_for_epub(filename=os.path.basename(x.get('href') or ''), mime=mt)
                if nmt != mt:
                    x.set('media-type', nmt)

    def workaround_nook_cover_bug(self, root: _Element) -> None:  # {{{
        cov = root.xpath('//*[local-name() = "meta" and @name="cover" and @content != "cover"]')

        def manifest_items_with_id(id_: str) -> list[_Element]:
            return root.xpath(f'//*[local-name() = "manifest"]/*[local-name() = "item"  and @id="{id_}"]')

        if len(cov) == 1:
            cov = cov[0]
            covid = cov.get('content', '')

            if covid:
                manifest_item = manifest_items_with_id(covid)
                if len(manifest_item) == 1 and manifest_item[0].get('media-type', '').startswith('image/'):
                    self.log.warn('The cover image has an id != "cover". Renaming to work around bug in Nook Color')

                    from calibre.ebooks.oeb.base import uuid_id

                    newid = uuid_id()

                    for item in manifest_items_with_id('cover'):
                        item.set('id', newid)

                    for x in root.xpath('//*[@idref="cover"]'):
                        x.set('idref', newid)

                    manifest_item = manifest_item[0]
                    manifest_item.set('id', 'cover')
                    cov.set('content', 'cover')

    # }}}

    def workaround_pocketbook_cover_bug(self, root: _Element) -> None:  # {{{
        m = root.xpath('//*[local-name() = "manifest"]/*[local-name() = "item"  and @id="cover"]')
        if len(m) == 1:
            m = m[0]
            p = m.getparent()
            p.remove(m)
            p.insert(0, m)

    # }}}

    def migrate_lang_code(self, root: _Element) -> None:  # {{{
        from calibre.utils.localization import lang_as_iso639_1

        for lang in root.xpath('//*[local-name() = "language"]'):
            clc = lang_as_iso639_1(lang.text)
            if clc:
                lang.text = clc

    # }}}
