#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals


from lxml import etree

# resolve_entities is turned off as entities can cause
# reads of local files, for example:
# <!DOCTYPE foo [ <!ENTITY passwd SYSTEM "file:///etc/passwd" >]>
SAFE_XML_PARSER = etree.XMLParser(recover=True, no_network=True, resolve_entities=False)
SAFE_XML_PARSER_NO_RECOVER = etree.XMLParser(recover=False, no_network=True, resolve_entities=False)
fs = etree.fromstring


def safe_xml_fromstring(string_or_bytes, recover=True):
    return fs(string_or_bytes, SAFE_XML_PARSER if recover else SAFE_XML_PARSER_NO_RECOVER)
