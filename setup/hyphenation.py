#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
# License: GPLv3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>
from __future__ import absolute_import, division, print_function, unicode_literals

import glob
import hashlib
import json
import os
import shutil
import tarfile
from io import BytesIO
from zipfile import ZipFile

from setup import Command, download_securely

URL = 'https://github.com/LibreOffice/dictionaries/archive/master.zip'


def locales_from_dicts(dicts):
    ans = {}
    for path in dicts:
        name = bname = os.path.basename(path)
        name = name[len('hyph_'):-len('.dic')]
        ans[name.replace('-', '_')] = bname
    return ans


def locales_from_xcu(xcu, dicts):
    from lxml import etree
    with open(xcu, 'rb') as f:
        root = etree.fromstring(f.read())
    ans = {}
    dicts = {os.path.basename(x) for x in dicts}
    for value in root.xpath('//*[contains(text(),"DICT_HYPH")]'):
        node = value.getparent().getparent()
        locales = path = None
        for prop in node:
            name = prop.get('{http://openoffice.org/2001/registry}name')
            if name == 'Locales':
                locales = [x.replace('-', '_') for x in prop[0].text.split()]
            elif name == 'Locations':
                path = prop[0].text.strip().split('/')[-1]
        if locales and path in dicts:
            for locale in locales:
                ans[locale] = path
    return ans


def process_dictionaries(src, output_dir):
    locale_data = {}
    for x in os.listdir(src):
        q = os.path.join(src, x)
        if not os.path.isdir(q):
            continue
        dicts = tuple(glob.glob(os.path.join(q, 'hyph_*.dic')))
        if not dicts:
            continue
        xcu = os.path.join(q, 'dictionaries.xcu')
        locales = (
            locales_from_xcu(xcu, dicts) if os.path.exists(xcu) else
            locales_from_dicts(dicts))
        if locales:
            locale_data.update(locales)
            for d in dicts:
                shutil.copyfile(
                    d, os.path.join(output_dir, os.path.basename(d)))
    data = json.dumps(locale_data, indent=2)
    if not isinstance(data, bytes):
        data = data.encode('utf-8')
    with open(os.path.join(output_dir, 'locales.json'), 'wb') as f:
        f.write(data)


def compress_tar(buf, outf):
    buf.seek(0)
    try:
        from calibre_lzma.xz import compress
    except ImportError:
        import lzma
        outf.write(lzma.compress(buf.getvalue(), preset=9 | lzma.PRESET_EXTREME))
    else:
        compress(buf, outf)


class Hyphenation(Command):

    description = 'Download the hyphenation dictionaries'

    def add_options(self, parser):
        pass
        # parser.add_option('--path-to-mathjax', help='Path to the MathJax source code')

    @property
    def hyphenation_dir(self):
        return self.j(self.RESOURCES, 'hyphenation')

    def clean(self):
        if os.path.exists(self.hyphenation_dir):
            shutil.rmtree(self.hyphenation_dir)

    def run(self, opts):
        self.clean()
        os.makedirs(self.hyphenation_dir)
        self.info('Downloading hyphenation dictionaries...')
        with self.temp_dir() as src, ZipFile(BytesIO(download_securely(URL))) as zf, self.temp_dir() as output_dir:
            zf.extractall(src)
            if len(os.listdir(src)) == 1:
                src = os.path.join(src, os.listdir(src)[0])
            process_dictionaries(src, output_dir)
            dics = sorted(x for x in os.listdir(output_dir) if x.endswith('.dic'))
            m = hashlib.sha1()
            for dic in dics:
                with open(os.path.join(output_dir, dic), 'rb') as f:
                    m.update(f.read())
            hsh = type('')(m.hexdigest())
            buf = BytesIO()
            with tarfile.TarFile(fileobj=buf, mode='w') as tf:
                for dic in dics:
                    with open(os.path.join(output_dir, dic), 'rb') as df:
                        tinfo = tf.gettarinfo(arcname=dic, fileobj=df)
                        tinfo.mtime = 0
                        tinfo.uid = tinfo.gid = 1000
                        tinfo.uname = tinfo.gname = 'kovid'
                        tf.addfile(tinfo, df)
            with open(os.path.join(self.hyphenation_dir, 'dictionaries.tar.xz'), 'wb') as f:
                compress_tar(buf, f)
            with open(os.path.join(self.hyphenation_dir, 'sha1sum'), 'w') as f:
                f.write(hsh)
            shutil.copy(os.path.join(output_dir, 'locales.json'), self.hyphenation_dir)
