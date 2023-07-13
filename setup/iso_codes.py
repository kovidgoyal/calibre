#!/usr/bin/env python
# License: GPLv3 Copyright: 2023, Kovid Goyal <kovid at kovidgoyal.net>

from setup import download_securely
import zipfile
from io import BytesIO


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


iso_data = ISOData()
