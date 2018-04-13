#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2018, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

from calibre.ebooks.metadata.opf_2_to_3 import upgrade_metadata


def epub_2_to_3(container, report):
    upgrade_metadata(container.opf)
    container.dirty(container.opf_name)
    container.opf.set('version', '3.0')


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
