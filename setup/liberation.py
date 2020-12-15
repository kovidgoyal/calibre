#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
# License: GPLv3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>
from __future__ import absolute_import, division, print_function, unicode_literals

import glob
import os

from setup.revendor import ReVendor


class LiberationFonts(ReVendor):

    description = 'Download the Liberation fonts'
    NAME = 'liberation_fonts'
    TAR_NAME = 'liberation-fonts'
    VERSION = '2.1.1'
    DOWNLOAD_URL = 'https://github.com/liberationfonts/liberation-fonts/files/4743886/liberation-fonts-ttf-%s.tar.gz' % VERSION

    @property
    def vendored_dir(self):
        return self.j(self.RESOURCES, 'fonts', 'liberation')

    def run(self, opts):
        self.clean()
        os.makedirs(self.vendored_dir)
        with self.temp_dir() as dl_src:
            src = opts.path_to_hyphenation or self.download_vendor_release(dl_src, opts.hyphenation_url)
            font_files = glob.glob(os.path.join(src, '*/Liberation*.ttf'))
            if not font_files:
                raise SystemExit(f'No font files found in {src}')

            for x in font_files:
                self.add_file(x, os.path.basename(x))
