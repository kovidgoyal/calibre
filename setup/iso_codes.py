#!/usr/bin/env python
# License: GPLv3 Copyright: 2023, Kovid Goyal <kovid at kovidgoyal.net>

import fnmatch
import os
import shutil
import time
import zipfile
from io import BytesIO

from setup import download_securely


class ISOData:
    URL = 'https://salsa.debian.org/iso-codes-team/iso-codes/-/archive/main/iso-codes-main.zip'

    def __init__(self):
        self._zip_data = None

    @property
    def zip_data(self):
        if self._zip_data is None:
            self._zip_data = BytesIO(download_securely(self.URL))
        return self._zip_data

    def db_data(self, name: str) -> bytes:
        with zipfile.ZipFile(self.zip_data) as zf:
            with zf.open(f'iso-codes-main/data/{name}') as f:
                return f.read()

    def extract_po_files(self, name: str, output_dir: str) -> None:
        name = name.split('.', 1)[0]
        pat = f'iso-codes-main/{name}/*.po'
        with zipfile.ZipFile(self.zip_data) as zf:
            for name in fnmatch.filter(zf.namelist(), pat):
                dest = os.path.join(output_dir, name.split('/')[-1])
                zi = zf.getinfo(name)
                with zf.open(zi) as src, open(dest, 'wb') as d:
                    shutil.copyfileobj(src, d)
                date_time = time.mktime(zi.date_time + (0, 0, -1))
                os.utime(dest, (date_time, date_time))

iso_data = ISOData()
