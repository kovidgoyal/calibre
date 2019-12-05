#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>


import errno
import json
import os
import tarfile
from io import BytesIO

from calibre.constants import cache_dir
from calibre.ptempfile import TemporaryDirectory
from calibre.utils.localization import lang_as_iso639_1
from polyglot.builtins import iteritems
from polyglot.functools import lru_cache


def locale_map():
    ans = getattr(locale_map, 'ans', None)
    if ans is None:
        ans = locale_map.ans = {k.lower(): v for k, v in iteritems(json.loads(P('hyphenation/locales.json', data=True)))}
    return ans


@lru_cache()
def dictionary_name_for_locale(loc):
    loc = loc.lower().replace('-', '_')
    lmap = locale_map()
    if loc in lmap:
        return lmap[loc]
    parts = loc.split('_')
    if len(parts) > 2:
        loc = '_'.join(parts[:2])
        if loc in lmap:
            return lmap[loc]
    loc = lang_as_iso639_1(parts[0])
    if not loc:
        return
    if loc in lmap:
        return lmap[loc]
    if loc == 'en':
        return lmap['en_us']
    if loc == 'de':
        return lmap['de_de']
    if loc == 'es':
        return lmap['es_es']
    q = loc + '_'
    for k, v in iteritems(lmap):
        if k.startswith(q):
            return lmap[k]


def extract_dicts(cache_path):
    with TemporaryDirectory(dir=cache_path) as tdir:
        try:
            from calibre_lzma.xz import decompress
        except ImportError:
            tf = tarfile.open(P('hyphenation/dictionaries.tar.xz'))
        else:
            buf = BytesIO()
            decompress(P('hyphenation/dictionaries.tar.xz', data=True), outfile=buf)
            buf.seek(0)
            tf = tarfile.TarFile(fileobj=buf)
        with tf:
            tf.extractall(tdir)
        dest = os.path.join(cache_path, 'f')
        with TemporaryDirectory(dir=cache_path) as trash:
            try:
                os.rename(dest, os.path.join(trash, 'f'))
            except EnvironmentError as err:
                if err.errno != errno.ENOENT:
                    raise
            os.rename(tdir, dest)
    is_cache_up_to_date.updated = True


def is_cache_up_to_date(cache_path):
    if getattr(is_cache_up_to_date, 'updated', False):
        return True
    hsh = P('hyphenation/sha1sum', data=True)
    try:
        with open(os.path.join(cache_path, 'f', 'sha1sum'), 'rb') as f:
            return f.read() == hsh
    except EnvironmentError:
        pass
    return False


@lru_cache()
def get_cache_path(cd):
    cache_path = os.path.join(cd, 'hyphenation')
    try:
        os.makedirs(cache_path)
    except EnvironmentError as err:
        if err.errno != errno.EEXIST:
            raise
    return cache_path


def path_to_dictionary(dictionary_name, cache_callback=None):
    cd = getattr(path_to_dictionary, 'cache_dir', None) or cache_dir()
    cache_path = get_cache_path(cd)
    if not is_cache_up_to_date(cache_path):
        extract_dicts(cache_path)
        if cache_callback is not None:
            cache_callback()
    return os.path.join(cache_path, 'f', dictionary_name)
