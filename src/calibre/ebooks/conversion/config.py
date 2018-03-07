#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, ast

from calibre.utils.config import config_dir
from calibre.utils.lock import ExclusiveFile
from calibre import sanitize_file_name
from calibre.customize.conversion import OptionRecommendation


config_dir = os.path.join(config_dir, 'conversion')
if not os.path.exists(config_dir):
    os.makedirs(config_dir)


def name_to_path(name):
    return os.path.join(config_dir, sanitize_file_name(name)+'.py')


def save_defaults(name, recs):
    path = name_to_path(name)
    raw = str(recs)
    with open(path, 'wb'):
        pass
    with ExclusiveFile(path) as f:
        f.write(raw)


def load_defaults(name):
    path = name_to_path(name)
    if not os.path.exists(path):
        open(path, 'wb').close()
    with ExclusiveFile(path) as f:
        raw = f.read()
    r = GuiRecommendations()
    if raw:
        r.from_string(raw)
    return r


def save_specifics(db, book_id, recs):
    raw = str(recs)
    db.set_conversion_options(book_id, 'PIPE', raw)


def load_specifics(db, book_id):
    raw = db.conversion_options(book_id, 'PIPE')
    r = GuiRecommendations()
    if raw:
        r.from_string(raw)
    return r


def delete_specifics(db, book_id):
    db.delete_conversion_options(book_id, 'PIPE')


class GuiRecommendations(dict):

    def __new__(cls, *args):
        dict.__new__(cls)
        obj = super(GuiRecommendations, cls).__new__(cls, *args)
        obj.disabled_options = set([])
        return obj

    def to_recommendations(self, level=OptionRecommendation.LOW):
        ans = []
        for key, val in self.items():
            ans.append((key, val, level))
        return ans

    def __str__(self):
        ans = ['{']
        for key, val in self.items():
            ans.append('\t'+repr(key)+' : '+repr(val)+',')
        ans.append('}')
        return '\n'.join(ans)

    def from_string(self, raw):
        try:
            d = ast.literal_eval(raw)
        except Exception:
            pass
        else:
            if d:
                self.update(d)

    def merge_recommendations(self, get_option, level, options,
            only_existing=False):
        for name in options:
            if only_existing and name not in self:
                continue
            opt = get_option(name)
            if opt is None:
                continue
            if opt.level == OptionRecommendation.HIGH:
                self[name] = opt.recommended_value
                self.disabled_options.add(name)
            elif opt.level > level or name not in self:
                self[name] = opt.recommended_value
