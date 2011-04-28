# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os

from lxml import etree

from calibre.customize.conversion import OutputFormatPlugin, \
    OptionRecommendation
from calibre.ptempfile import TemporaryDirectory
from calibre.utils.zipfile import ZipFile

class HTMLZOutput(OutputFormatPlugin):

    name = 'HTMLZ Output'
    author = 'John Schember'
    file_type = 'htmlz'

    options = set([
        OptionRecommendation(name='htmlz_css_type', recommended_value='class',
            level=OptionRecommendation.LOW,
            choices=['class', 'inline', 'tag'],
            help=_('Specify the handling of CSS. Default is class.\n'
                   'class: Use CSS classes and have elements reference them.\n'
                   'inline: Write the CSS as an inline style attribute.\n'
                   'tag: Turn as many CSS styles as possible into HTML tags.'
            )),
        OptionRecommendation(name='htmlz_class_style', recommended_value='external',
            level=OptionRecommendation.LOW,
            choices=['external', 'inline'],
            help=_('How to handle the CSS when using css-type = \'class\'.\n'
                   'Default is external.\n'
                   'external: Use an external CSS file that is linked in the document.\n'
                   'inline: Place the CSS in the head section of the document.'
            )),
    ])

    def convert(self, oeb_book, output_path, input_plugin, opts, log):
        from calibre.ebooks.oeb.base import OEB_IMAGES, SVG_MIME

        # HTML
        if opts.htmlz_css_type == 'inline':
            from calibre.ebooks.htmlz.oeb2html import OEB2HTMLInlineCSSizer
            OEB2HTMLizer = OEB2HTMLInlineCSSizer
        elif opts.htmlz_css_type == 'tag':
            from calibre.ebooks.htmlz.oeb2html import OEB2HTMLNoCSSizer
            OEB2HTMLizer = OEB2HTMLNoCSSizer
        else:
            from calibre.ebooks.htmlz.oeb2html import OEB2HTMLClassCSSizer as OEB2HTMLizer

        with TemporaryDirectory('_htmlz_output') as tdir:
            htmlizer = OEB2HTMLizer(log)
            html = htmlizer.oeb2html(oeb_book, opts)

            with open(os.path.join(tdir, 'index.html'), 'wb') as tf:
                tf.write(html)

            # CSS
            if opts.htmlz_css_type == 'class' and opts.htmlz_class_style == 'external':
                with open(os.path.join(tdir, 'style.css'), 'wb') as tf:
                    tf.write(htmlizer.get_css(oeb_book))

            # Images
            images = htmlizer.images
            if images:
                if not os.path.exists(os.path.join(tdir, 'images')):
                    os.makedirs(os.path.join(tdir, 'images'))
                for item in oeb_book.manifest:
                    if item.media_type in OEB_IMAGES and item.href in images:
                        if item.media_type == SVG_MIME:
                            data = unicode(etree.tostring(item.data, encoding=unicode))
                        else:
                            data = item.data
                        fname = os.path.join(tdir, 'images', images[item.href])
                        with open(fname, 'wb') as img:
                            img.write(data)

            # Metadata
            with open(os.path.join(tdir, 'metadata.opf'), 'wb') as mdataf:
                mdataf.write(etree.tostring(oeb_book.metadata.to_opf1()))

            htmlz = ZipFile(output_path, 'w')
            htmlz.add_dir(tdir)
