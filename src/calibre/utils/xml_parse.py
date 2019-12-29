#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals


from lxml import etree
import threading


# resolve_entities is turned off as entities can cause
# reads of local files, for example:
# <!DOCTYPE foo [ <!ENTITY passwd SYSTEM "file:///etc/passwd" >]>


class GlobalParserTLS(threading.local):

    def __call__(self, recover):
        parsers = getattr(self, 'parsers', None)
        if parsers is None:
            self.parsers = parsers = {
                True: etree.XMLParser(recover=True, no_network=True, resolve_entities=False),
                False: etree.XMLParser(recover=False, no_network=True, resolve_entities=False)
            }
        return parsers[recover]


_global_tls = GlobalParserTLS()
fs = etree.fromstring


def safe_xml_fromstring(string_or_bytes, recover=True):
    return fs(string_or_bytes, _global_tls(recover))
