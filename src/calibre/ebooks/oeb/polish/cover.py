#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import shutil

from calibre.ebooks.oeb.base import OPF

def set_azw3_cover(container, cover_path, report):
    name = None
    found = True
    for gi in container.opf_xpath('//opf:guide/opf:reference[@href and contains(@type, "cover")]'):
        href = gi.get('href')
        name = container.href_to_name(href, container.opf_name)
        container.remove_from_xml(gi)
    if name is None or not container.has_name(name):
        item = container.generate_item(name='cover.jpeg', id_prefix='cover')
        name = container.href_to_name(item.get('href'), container.opf_name)
        found = False
    href = container.name_to_href(name, container.opf_name)
    guide = container.opf_xpath('//opf:guide')[0]
    container.insert_into_xml(guide, guide.makeelement(
        OPF('reference'), href=href, type='cover'))
    shutil.copyfile(cover_path, container.name_to_abspath(name))
    container.dirty(container.opf_name)
    report('Cover updated' if found else 'Cover inserted')

def set_cover(container, cover_path, report):
    if container.book_type == 'azw3':
        set_azw3_cover(container, cover_path, report)

