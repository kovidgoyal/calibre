#!/usr/bin/env python
# License: GPLv3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>

import glob
import os

from setup.revendor import ReVendor


class LiberationFonts(ReVendor):

    description = 'Download the Liberation fonts'
    NAME = 'liberation_fonts'
    TAR_NAME = 'liberation-fonts'
    VERSION = '2.1.3'
    DOWNLOAD_URL = 'https://github.com/liberationfonts/liberation-fonts/files/6026893/liberation-fonts-ttf-%s.tar.gz' % VERSION

    @property
    def vendored_dir(self):
        return self.j(self.RESOURCES, 'fonts', 'liberation')

    @property
    def version_file(self):
        return self.j(self.vendored_dir, 'version.txt')

    def already_present(self):
        if os.path.exists(self.version_file):
            with open(self.version_file) as f:
                return f.read() == self.VERSION
        return False

    def run(self, opts):
        if not opts.system_liberation_fonts and self.already_present():
            self.info('Liberation Fonts already present in the resources directory, not downloading')
            return
        self.clean()
        os.makedirs(self.vendored_dir)
        self.use_symlinks = opts.system_liberation_fonts
        with self.temp_dir() as dl_src:
            src = opts.path_to_liberation_fonts or self.download_vendor_release(dl_src, opts.liberation_fonts_url)
            font_files = glob.glob(os.path.join(src, 'Liberation*.ttf'))
            if not font_files:
                raise SystemExit(f'No font files found in {src}')

            for x in font_files:
                self.add_file(x, os.path.basename(x))
        with open(self.j(self.vendored_dir, 'version.txt'), 'w') as f:
            f.write(self.VERSION)
