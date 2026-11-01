# License: GPLv3 Copyright: 2008, Marshall T. Vandegrift <llasram@gmail.com>

"""
Add page mapping information to an EPUB book.
"""

import re
from itertools import count
from typing import TYPE_CHECKING

from lxml.etree import XPath, _Element

from calibre.ebooks.oeb.base import XHTML_NS, OEBBook

if TYPE_CHECKING:
    from collections.abc import Callable
    from optparse import Values

NSMAP = {'h': XHTML_NS, 'html': XHTML_NS, 'xhtml': XHTML_NS}
PAGE_RE = re.compile(r'page', re.IGNORECASE)
ROMAN_RE = re.compile(r'^[ivxlcdm]+$', re.IGNORECASE)


def filter_name(name: str) -> str:
    name = name.strip()
    name = PAGE_RE.sub('', name)
    for word in name.split():
        if word.isdigit() or ROMAN_RE.match(word):
            name = word
            break
    return name


def build_name_for(expr: str | None) -> Callable[[_Element], str]:
    if not expr:
        counter = count(1)
        return lambda elem: str(next(counter))
    selector = XPath(expr, namespaces=NSMAP)

    def name_for(elem: _Element) -> str:
        results = selector(elem)
        if not results:
            return ''
        name = ' '.join(results)
        return filter_name(name)

    return name_for


def add_page_map(opfpath: str, opts: Values) -> None:
    from calibre.ebooks.oeb.reader import OEBReader
    from calibre.utils.logging import default_log

    oeb = OEBBook(default_log)
    OEBReader()(oeb, opfpath)
    selector = XPath(opts.page, namespaces=NSMAP)
    name_for = build_name_for(opts.page_names)
    idgen = (f'calibre-page-{n}' for n in count(1))
    for item in oeb.spine:
        data = item.data
        assert isinstance(data, _Element)  # spine items are parsed (X)HTML documents
        for elem in selector(data):
            name = name_for(elem)
            id = elem.get('id', None)
            if id is None:
                id = elem.attrib['id'] = next(idgen)
            href = f'{item.href}#{id}'
            oeb.pages.add(name, href)
    # writer = None  # DirWriter(version='2.0', page_map=True)
    # writer.dump(oeb, opfpath)
