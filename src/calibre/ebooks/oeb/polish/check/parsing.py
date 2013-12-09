#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from lxml.etree import XMLParser, fromstring, XMLSyntaxError

from calibre.ebooks.oeb.polish.check.base import BaseError
from calibre.ebooks.oeb.base import OEB_DOCS

class XMLParseError(BaseError):

    HELP = _('A parsing error in an XML file means that the XML syntax in the file is incorrect.'
             ' Such a file will most probably not open in an ebook reader. These errors can '
             ' usually be fixed automatically, however, automatic fixing can sometimes '
             ' "do the wrong thing".')

    def __init__(self, msg, *args, **kwargs):
        BaseError.__init__(self, 'Parsing failed: ' + msg, *args, **kwargs)

class HTMLParseError(XMLParseError):

    HELP = _('A parsing error in an HTML file means that the HTML syntax is incorrect.'
             ' Most readers will automatically ignore such errors, but they may result in '
             ' incorrect display of content. These errors can usually be fixed automatically,'
             ' however, automatic fixing can sometimes "do the wrong thing".')

def check_xml_parsing(name, mt, raw):
    parser = XMLParser(recover=False)
    errcls = HTMLParseError if mt in OEB_DOCS else XMLParseError

    try:
        fromstring(raw, parser=parser)
    except XMLSyntaxError as err:
        try:
            line, col = err.position
        except:
            line = col = None
        return [errcls(err.message, name, line, col)]
    except Exception as err:
        return [errcls(err.message, name)]
    return []

