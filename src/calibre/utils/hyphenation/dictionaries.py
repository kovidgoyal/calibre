#!/usr/bin/env python
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
from calibre.utils.lock import ExclusiveFile
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


@lru_cache(maxsize=2)
def expected_hash():
    return P('hyphenation/sha1sum', data=True, allow_user_override=False)


def extract_dicts(cache_path):
    dict_tarball = P('hyphenation/dictionaries.tar.xz', allow_user_override=False)
    with TemporaryDirectory(dir=cache_path) as tdir:
        try:
            from calibre_lzma.xz import decompress
        except ImportError:
            tf = tarfile.open(dict_tarball)
        else:
            buf = BytesIO()
            with lopen(dict_tarball, 'rb') as f:
                data = f.read()
            decompress(data, outfile=buf)
            buf.seek(0)
            tf = tarfile.TarFile(fileobj=buf)
        with tf:
            tf.extractall(tdir)
        with open(os.path.join(tdir, 'sha1sum'), 'wb') as f:
            f.write(expected_hash())
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
    try:
        with open(os.path.join(cache_path, 'f', 'sha1sum'), 'rb') as f:
            actual_hash = f.read()
        if actual_hash == expected_hash():
            is_cache_up_to_date.updated = True
            return True
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
    with ExclusiveFile(os.path.join(cache_path, 'lock')):
        if not is_cache_up_to_date(cache_path):
            extract_dicts(cache_path)
            if cache_callback is not None:
                cache_callback()
    return os.path.join(cache_path, 'f', dictionary_name)
