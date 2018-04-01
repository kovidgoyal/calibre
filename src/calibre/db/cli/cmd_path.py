#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2018, Nikita Sirgienko <warquark@gmail.com>

from __future__ import division, print_function, unicode_literals

from calibre.db.cli import integers_from_string

import os

def option_parser(get_parser, args):
    # TODO: translation (update po?)
    # TODO: more options?
    parser = get_parser(
        _(
            '''\
%prog open ids

Print absolute paths of one of available formats by book ids.
'''
        )
    )
    return parser

def main(opts, args, dbctx):
    if len(args) < 1:
        raise SystemExit(_('You must specify some ids'))
    book_ids = set()
    for arg in args:
        book_ids |= set(integers_from_string(arg))
    # TODO: is it normal? Use another API from dbctx?
    db = dbctx.db
    for i, book_id in enumerate(book_ids):
        formats = db.get_field(book_id,'formats', None, True)
        if formats != None:
            #TODO: add option for prefered format?
            format = formats[0]
            # TODO: Platform independent path escaping!
            path=db.format_abspath(book_id, format, True)
            print(path)
        #else:
            #print(_("Id %s doesn't contain in library") % book_id)
    return 0