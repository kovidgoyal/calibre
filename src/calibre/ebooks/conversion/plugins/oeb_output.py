from __future__ import with_statement
__license__ = 'GPL 3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, re


from calibre.customize.conversion import (OutputFormatPlugin,
        OptionRecommendation)
from calibre import CurrentDir

class OEBOutput(OutputFormatPlugin):

    name = 'OEB Output'
    author = 'Kovid Goyal'
    file_type = 'oeb'

    recommendations = set([('pretty_print', True, OptionRecommendation.HIGH)])


    def convert(self, oeb_book, output_path, input_plugin, opts, log):
        from urllib import unquote
        from lxml import etree

        self.log, self.opts = log, opts
        if not os.path.exists(output_path):
            os.makedirs(output_path)
        from calibre.ebooks.oeb.base import OPF_MIME, NCX_MIME, PAGE_MAP_MIME
        with CurrentDir(output_path):
            results = oeb_book.to_opf2(page_map=True)
            for key in (OPF_MIME, NCX_MIME, PAGE_MAP_MIME):
                href, root = results.pop(key, [None, None])
                if root is not None:
                    if key == OPF_MIME:
                        try:
                            self.workaround_nook_cover_bug(root)
                        except:
                            self.log.exception('Something went wrong while trying to'
                                    ' workaround Nook cover bug, ignoring')
                        try:
                            self.workaround_pocketbook_cover_bug(root)
                        except:
                            self.log.exception('Something went wrong while trying to'
                                    ' workaround Pocketbook cover bug, ignoring')
                        self.migrate_lang_code(root)
                    raw = etree.tostring(root, pretty_print=True,
                            encoding='utf-8', xml_declaration=True)
                    if key == OPF_MIME:
                        # Needed as I can't get lxml to output opf:role and
                        # not output <opf:metadata> as well
                        raw = re.sub(r'(<[/]{0,1})opf:', r'\1', raw)
                    with open(href, 'wb') as f:
                        f.write(raw)

            for item in oeb_book.manifest:
                path = os.path.abspath(unquote(item.href))
                dir = os.path.dirname(path)
                if not os.path.exists(dir):
                    os.makedirs(dir)
                with open(path, 'wb') as f:
                    f.write(str(item))
                item.unload_data_from_memory(memory=path)

    def workaround_nook_cover_bug(self, root): # {{{
        cov = root.xpath('//*[local-name() = "meta" and @name="cover" and'
                ' @content != "cover"]')

        def manifest_items_with_id(id_):
            return root.xpath('//*[local-name() = "manifest"]/*[local-name() = "item" '
                ' and @id="%s"]'%id_)

        if len(cov) == 1:
            cov = cov[0]
            covid = cov.get('content', '')

            if covid:
                manifest_item = manifest_items_with_id(covid)
                if len(manifest_item) == 1 and \
                        manifest_item[0].get('media-type',
                                '').startswith('image/'):
                    self.log.warn('The cover image has an id != "cover". Renaming'
                            ' to work around bug in Nook Color')

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

    def workaround_pocketbook_cover_bug(self, root): # {{{
        m = root.xpath('//*[local-name() = "manifest"]/*[local-name() = "item" '
                ' and @id="cover"]')
        if len(m) == 1:
            m = m[0]
            p = m.getparent()
            p.remove(m)
            p.insert(0, m)
    # }}}

    def migrate_lang_code(self, root): # {{{
        from calibre.utils.localization import lang_as_iso639_1
        for lang in root.xpath('//*[local-name() = "language"]'):
            clc = lang_as_iso639_1(lang.text)
            if clc:
                lang.text = clc
    # }}}

