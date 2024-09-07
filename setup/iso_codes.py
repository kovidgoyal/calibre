#!/usr/bin/env python
# License: GPLv3 Copyright: 2023, Kovid Goyal <kovid at kovidgoyal.net>

import fnmatch
import optparse
import os
import shutil
import time
import zipfile
from contextlib import suppress
from functools import lru_cache
from io import BytesIO

from setup import Command, download_securely


@lru_cache(2)
def iso_codes_data():
    URL = 'https://download.calibre-ebook.com/iso-codes.zip'
    return download_securely(URL)


class ISOData(Command):
    description = 'Get ISO codes name localization data'
    top_level_filename =  'iso-codes-main'
    _zip_data = None

    def add_options(self, parser):
        with suppress(optparse.OptionConflictError):  # ignore if option already added
            parser.add_option('--path-to-isocodes', help='Path to previously downloaded iso-codes-main.zip')

    def run(self, opts):
        if self._zip_data is None and opts.path_to_isocodes:
            with open(opts.path_to_isocodes, 'rb') as f:
                self._zip_data = f.read()
            # get top level directory
            top = {item.split('/')[0] for item in zipfile.ZipFile(self.zip_data).namelist()}
            assert len(top) == 1
            self.top_level_filename = top.pop()

    @property
    def zip_data(self):
        return self._zip_data or iso_codes_data()

    def db_data(self, name: str) -> bytes:
        with zipfile.ZipFile(BytesIO(self.zip_data)) as zf:
            with zf.open(f'{self.top_level_filename}/data/{name}') as f:
                return f.read()

    def extract_po_files(self, name: str, output_dir: str) -> None:
        name = name.split('.', 1)[0]
        pat = f'{self.top_level_filename}/{name}/*.po'
        with zipfile.ZipFile(BytesIO(self.zip_data)) as zf:
            for name in fnmatch.filter(zf.namelist(), pat):
                dest = os.path.join(output_dir, name.split('/')[-1])
                zi = zf.getinfo(name)
                with zf.open(zi) as src, open(dest, 'wb') as d:
                    shutil.copyfileobj(src, d)
                date_time = time.mktime(zi.date_time + (0, 0, -1))
                os.utime(dest, (date_time, date_time))


iso_data = ISOData()
