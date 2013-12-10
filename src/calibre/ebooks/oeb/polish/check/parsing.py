#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import re

from lxml.etree import XMLParser, fromstring, XMLSyntaxError

from calibre.ebooks.html_entities import html5_entities
from calibre.ebooks.oeb.polish.utils import PositionFinder
from calibre.ebooks.oeb.polish.check.base import BaseError, WARN
from calibre.ebooks.oeb.base import OEB_DOCS

HTML_ENTITTIES = frozenset(html5_entities)
XML_ENTITIES = {'lt', 'gt', 'amp', 'apos', 'quot'}
ALL_ENTITIES = HTML_ENTITTIES | XML_ENTITIES

replace_pat = re.compile('&(%s);' % '|'.join(re.escape(x) for x in sorted((HTML_ENTITTIES - XML_ENTITIES))))

class XMLParseError(BaseError):

    is_parsing_error = True

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

class NamedEntities(BaseError):

    level = WARN
    INDIVIDUAL_FIX = _('Replace all named entities with their character equivalents in this file')
    HELP = _('Named entities are often only incompletely supported by various book reading software.'
             ' Therefore, it is best to not use them, replacing them with the actual characters they'
             ' represent. This can be done automatically.')

    def __init__(self, name):
        BaseError.__init__(self, _('Named entities present'), name)

    def __call__(self, container):
        raw = container.raw_data(self.name)
        nraw = replace_pat.sub(lambda m:html5_entities[m.group(1)], raw)
        with container.open(self.name, 'wb') as f:
            f.write(nraw.encode('utf-8'))
        return True

class BadEntity(BaseError):

    HELP = _('This is an invalid (unrecognized) entity. Replace it with whatever'
             ' text it is supposed to have represented.')

    def __init__(self, ent, name, lnum, col):
        BaseError.__init__(self, _('Invalid entity: %s') % ent, name, lnum, col)


class EntitityProcessor(object):

    def __init__(self, mt):
        self.entities = ALL_ENTITIES if mt in OEB_DOCS else XML_ENTITIES
        self.ok_named_entities = []
        self.bad_entities = []

    def __call__(self, m):
        val = m.group(1).decode('ascii')
        if val in XML_ENTITIES:
            # Leave XML entities alone
            return m.group()

        if val.startswith('#'):
            nval = val[1:]
            try:
                if nval.startswith('x'):
                    int(nval[1:], 16)
                else:
                    int(nval, 10)
            except ValueError:
                # Invalid numerical entity
                self.bad_entities.append((m.start(), m.group()))
                return b' ' * len(m.group())
            return m.group()

        if val in self.entities:
            # Known named entity, report it
            self.ok_named_entities.append(m.start())
        else:
            self.bad_entities.append((m.start(), m.group()))
        return b' ' * len(m.group())

entity_pat = re.compile(br'&(#{0,1}[a-zA-Z0-9]{1,8});')

def check_xml_parsing(name, mt, raw):
    raw = raw.replace(b'\r\n', b'\n').replace(b'\r', b'\n')
    # Get rid of entities as named entities trip up the XML parser
    eproc = EntitityProcessor(mt)
    eraw = entity_pat.sub(eproc, raw)
    parser = XMLParser(recover=False)
    errcls = HTMLParseError if mt in OEB_DOCS else XMLParseError
    errors = []
    if eproc.ok_named_entities:
        errors.append(NamedEntities(name))
    if eproc.bad_entities:
        position = PositionFinder(raw)
        for offset, ent in eproc.bad_entities:
            lnum, col = position(offset)
            errors.append(BadEntity(ent, name, lnum, col))

    try:
        fromstring(eraw, parser=parser)
    except XMLSyntaxError as err:
        try:
            line, col = err.position
        except:
            line = col = None
        return errors + [errcls(err.message, name, line, col)]
    except Exception as err:
        return errors + [errcls(err.message, name)]

    return errors

