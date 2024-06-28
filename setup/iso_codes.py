#!/usr/bin/env python
# License: GPLv3 Copyright: 2023, Kovid Goyal <kovid at kovidgoyal.net>

import fnmatch
import optparse
import os
import shutil
import time
import zipfile
from contextlib import suppress
from io import BytesIO

from setup import Command, download_securely


class ISOData(Command):
    description = 'Get ISO codes name localization data'
    URL = 'https://salsa.debian.org/iso-codes-team/iso-codes/-/archive/main/iso-codes-main.zip'

    def add_options(self, parser):
        with suppress(optparse.OptionConflictError):  # ignore if option already added
            parser.add_option('--path-to-isocodes', help='Path to previously downloaded iso-codes-main.zip')

    def run(self, opts):
        if self._zip_data is None:
            if opts.path_to_isocodes:
                with open(opts.path_to_isocodes, 'rb') as f:
                    self._zip_data = BytesIO(f.read())
                # get top level directory
                top = {item.split('/')[0] for item in zipfile.ZipFile(self.zip_data).namelist()}
                assert len(top) == 1
                self.top_level = top.pop()
            else:
                self._zip_data = BytesIO(download_securely(self.URL))

    def __init__(self):
        super().__init__()
        self._zip_data = None
        self.top_level = 'iso-codes-main'

    @property
    def zip_data(self):
        return self._zip_data

    def db_data(self, name: str) -> bytes:
        with zipfile.ZipFile(self.zip_data) as zf:
            with zf.open(f'{self.top_level}/data/{name}') as f:
                return f.read()

    def extract_po_files(self, name: str, output_dir: str) -> None:
        name = name.split('.', 1)[0]
        pat = f'{self.top_level}/{name}/*.po'
        if self.zip_data is None:
            self._zip_data = BytesIO(download_securely(self.URL))
        with zipfile.ZipFile(self.zip_data) as zf:
            for name in fnmatch.filter(zf.namelist(), pat):
                dest = os.path.join(output_dir, name.split('/')[-1])
                zi = zf.getinfo(name)
                with zf.open(zi) as src, open(dest, 'wb') as d:
                    shutil.copyfileobj(src, d)
                date_time = time.mktime(zi.date_time + (0, 0, -1))
                os.utime(dest, (date_time, date_time))


iso_data = ISOData()
