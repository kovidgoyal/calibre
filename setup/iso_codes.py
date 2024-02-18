#!/usr/bin/env python
# License: GPLv3 Copyright: 2023, Kovid Goyal <kovid at kovidgoyal.net>

import fnmatch
import os
import shutil, time
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
            zip_file = os.getenv('ISOCODE_ZIP')
            if zip_file:
                with open(zip_file, "rb") as f:
                    self._zip_data = BytesIO(f.read())
            else:
                self._zip_data = BytesIO(download_securely(self.URL))
        return self._zip_data

    def db_data(self, name: str) -> bytes:
        with zipfile.ZipFile(self.zip_data) as zf:
            iso_version = os.getenv("ISOCODE_VERSION")
            if iso_version:
                dir = f"iso-codes-v{iso_version}"
            else:
                dir = "iso-codes-main"
            with zf.open(f'{dir}/data/{name}') as f:
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
