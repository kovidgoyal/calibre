'''
Add page mapping information to an EPUB book.
'''


__license__   = 'GPL v3'
__copyright__ = '2008, Marshall T. Vandegrift <llasram@gmail.com>'
__docformat__ = 'restructuredtext en'

import re
from itertools import count
from calibre.ebooks.oeb.base import XHTML_NS
from calibre.ebooks.oeb.base import OEBBook
from lxml.etree import XPath
from polyglot.builtins import unicode_type

NSMAP = {'h': XHTML_NS, 'html': XHTML_NS, 'xhtml': XHTML_NS}
PAGE_RE = re.compile(r'page', re.IGNORECASE)
ROMAN_RE = re.compile(r'^[ivxlcdm]+$', re.IGNORECASE)


def filter_name(name):
    name = name.strip()
    name = PAGE_RE.sub('', name)
    for word in name.split():
        if word.isdigit() or ROMAN_RE.match(word):
            name = word
            break
    return name


def build_name_for(expr):
    if not expr:
        counter = count(1)
        return lambda elem: unicode_type(next(counter))
    selector = XPath(expr, namespaces=NSMAP)

    def name_for(elem):
        results = selector(elem)
        if not results:
            return ''
        name = ' '.join(results)
        return filter_name(name)
    return name_for


def add_page_map(opfpath, opts):
    oeb = OEBBook(opfpath)
    selector = XPath(opts.page, namespaces=NSMAP)
    name_for = build_name_for(opts.page_names)
    idgen = ("calibre-page-%d" % n for n in count(1))
    for item in oeb.spine:
        data = item.data
        for elem in selector(data):
            name = name_for(elem)
            id = elem.get('id', None)
            if id is None:
                id = elem.attrib['id'] = next(idgen)
            href = '#'.join((item.href, id))
            oeb.pages.add(name, href)
    writer = None  # DirWriter(version='2.0', page_map=True)
    writer.dump(oeb, opfpath)
