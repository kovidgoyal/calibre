#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

import os
import re

from calibre import extract, filesystem_encoding, walk

ARCHIVE_FMTS = ('zip', 'rar', 'oebzip')


def unarchive(path, tdir):
    extract(path, tdir)
    files = list(walk(tdir))
    files = [f if isinstance(f, str) else f.decode(filesystem_encoding)
            for f in files]
    from calibre.customize.ui import available_input_formats
    fmts = set(available_input_formats())
    fmts -= {'htm', 'html', 'xhtm', 'xhtml'}
    fmts -= set(ARCHIVE_FMTS)

    for ext in fmts:
        for f in files:
            if f.lower().endswith('.'+ext):
                if ext in ['txt', 'rtf'] and os.stat(f).st_size < 2048:
                    continue
                return f, ext
    return find_html_index(files)


def find_html_index(files):
    '''
    Given a list of files, find the most likely root HTML file in the
    list.
    '''
    html_pat = re.compile(r'\.(x){0,1}htm(l){0,1}$', re.IGNORECASE)
    html_files = [f for f in files if html_pat.search(f) is not None]
    if not html_files:
        raise ValueError(_('Could not find an e-book inside the archive'))
    html_files = [(f, os.stat(f).st_size) for f in html_files]
    html_files.sort(key=lambda x: x[1])
    html_files = [f[0] for f in html_files]
    for q in ('toc', 'index'):
        for f in html_files:
            if os.path.splitext(os.path.basename(f))[0].lower() == q:
                return f, os.path.splitext(f)[1].lower()[1:]
    return html_files[-1], os.path.splitext(html_files[-1])[1].lower()[1:]
