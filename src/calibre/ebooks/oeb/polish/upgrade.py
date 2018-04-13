#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2018, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

from calibre.ebooks.metadata.opf_2_to_3 import upgrade_metadata
from calibre.ebooks.oeb.base import OEB_DOCS, xpath


def add_properties(item, *props):
    existing = set((item.get('properties') or '').split())
    existing |= set(props)
    item.set('properties', ' '.join(sorted(existing)))


def collect_properties(container):
    for item in container.opf_xpath('//opf:manifest/opf:item[@href and @media-type]'):
        mt = item.get('media-type') or ''
        if mt.lower() not in OEB_DOCS:
            continue
        name = container.href_to_name(item.get('href'), container.opf_name)
        root = container.parsed(name)
        properties = set()
        container.dirty(name)  # Ensure entities are converted
        if xpath(root, '//svg:svg'):
            properties.add('svg')
        if xpath(root, '//h:script'):
            properties.add('scripted')
        if xpath(root, '//mathml:math'):
            properties.add('mathml')
        if xpath(root, '//epub:switch'):
            properties.add('switch')
        if properties:
            add_properties(item, *tuple(properties))


def epub_2_to_3(container, report):
    upgrade_metadata(container.opf)
    collect_properties(container)
    container.opf.set('version', '3.0')
    container.dirty(container.opf_name)


def upgrade_book(container, report):
    if container.book_type != 'epub' or container.opf_version_parsed.major >= 3:
        report(_('No upgrade needed'))
        return False
    epub_2_to_3(container, report)
    report(_('Updated EPUB from version 2 to 3'))
    return True


if __name__ == '__main__':
    from calibre.ebooks.oeb.polish.container import get_container
    from calibre.utils.logging import default_log
    default_log.filter_level = default_log.DEBUG
    inbook = sys.argv[-1]
    ebook = get_container(inbook, default_log)
    if upgrade_book(ebook, print):
        outbook = inbook.rpartition('.')[0] + '-upgraded.' + inbook.rpartition('.')[-1]
        ebook.commit(outbook)
        print('Upgraded book written to:', outbook)
