#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import os, sys

from calibre.ptempfile import TemporaryDirectory
from calibre.ebooks.conversion.plumber import Plumber
from calibre.ebooks.oeb.polish.container import Container, OEB_DOCS, OEB_STYLES
from calibre.ebooks.epub import initialize_container

from calibre.utils.logging import default_log
from polyglot.builtins import iteritems

IMPORTABLE = {'htm', 'xhtml', 'html', 'xhtm', 'docx'}


def auto_fill_manifest(container):
    manifest_id_map = container.manifest_id_map
    manifest_name_map = {v:k for k, v in iteritems(manifest_id_map)}

    for name, mt in iteritems(container.mime_map):
        if name not in manifest_name_map and not container.ok_to_be_unmanifested(name):
            mitem = container.generate_item(name, unique_href=False)
            gname = container.href_to_name(mitem.get('href'), container.opf_name)
            if gname != name:
                raise ValueError('This should never happen (gname=%r, name=%r, href=%r)' % (gname, name, mitem.get('href')))
            manifest_name_map[name] = mitem.get('id')
            manifest_id_map[mitem.get('id')] = name


def import_book_as_epub(srcpath, destpath, log=default_log):
    if not destpath.lower().endswith('.epub'):
        raise ValueError('Can only import books into the EPUB format, not %s' % (os.path.basename(destpath)))
    with TemporaryDirectory('eei') as tdir:
        tdir = os.path.abspath(os.path.realpath(tdir))  # Needed to handle the multiple levels of symlinks for /tmp on OS X
        plumber = Plumber(srcpath, tdir, log)
        plumber.setup_options()
        if srcpath.lower().endswith('.opf'):
            plumber.opts.dont_package = True
        if hasattr(plumber.opts, 'no_process'):
            plumber.opts.no_process = True
        plumber.input_plugin.for_viewer = True
        with plumber.input_plugin, open(plumber.input, 'rb') as inf:
            pathtoopf = plumber.input_plugin(inf, plumber.opts, plumber.input_fmt, log, {}, tdir)
        if hasattr(pathtoopf, 'manifest'):
            from calibre.ebooks.oeb.iterator.book import write_oebbook
            pathtoopf = write_oebbook(pathtoopf, tdir)

        c = Container(tdir, pathtoopf, log)
        auto_fill_manifest(c)
        # Auto fix all HTML/CSS
        for name, mt in iteritems(c.mime_map):
            if mt in set(OEB_DOCS) | set(OEB_STYLES):
                c.parsed(name)
                c.dirty(name)
        c.commit()

        zf = initialize_container(destpath, opf_name=c.opf_name)
        with zf:
            for name in c.name_path_map:
                zf.writestr(name, c.raw_data(name, decode=False))


if __name__ == '__main__':
    import_book_as_epub(sys.argv[-2], sys.argv[-1])
