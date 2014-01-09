#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import re

from lxml.etree import XMLParser, fromstring, XMLSyntaxError
import cssutils

from calibre import force_unicode, human_readable, prepare_string_for_xml
from calibre.ebooks.html_entities import html5_entities
from calibre.ebooks.oeb.polish.pretty import pretty_script_or_style as fix_style_tag
from calibre.ebooks.oeb.polish.utils import PositionFinder
from calibre.ebooks.oeb.polish.check.base import BaseError, WARN, ERROR, INFO
from calibre.ebooks.oeb.base import OEB_DOCS, XHTML_NS

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

class TooLarge(BaseError):

    level = INFO
    MAX_SIZE = 260 *1024
    HELP = _('This HTML file is larger than %s. Too large HTML files can cause performance problems'
             ' on some ebook readers. Consider splitting this file into smaller sections.') % human_readable(MAX_SIZE)

    def __init__(self, name):
        BaseError.__init__(self, _('File too large'), name)

class BadEntity(BaseError):

    HELP = _('This is an invalid (unrecognized) entity. Replace it with whatever'
             ' text it is supposed to have represented.')

    def __init__(self, ent, name, lnum, col):
        BaseError.__init__(self, _('Invalid entity: %s') % ent, name, lnum, col)

class BadNamespace(BaseError):

    INDIVIDUAL_FIX = _(
        'Run fix HTML on this file, which will automatically insert the correct namespace')

    def __init__(self, name, namespace):
        BaseError.__init__(self, _('Invalid or missing namespace'), name)
        self.HELP = prepare_string_for_xml(_(
            'This file has {0}. Its namespace must be {1}. Se the namespace by defining the xmlns'
            ' attribute on the <html> element, like this <html xmlns="{1}">').format(
                (_('incorrect namespace %s') % namespace) if namespace else _('no namespace'),
                XHTML_NS))

    def __call__(self, container):
        container.parsed(self.name)
        container.dirty(self.name)
        return True


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

def check_html_size(name, mt, raw):
    errors = []
    if len(raw) > TooLarge.MAX_SIZE:
        errors.append(TooLarge(name))
    return errors

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
        root = fromstring(eraw, parser=parser)
    except XMLSyntaxError as err:
        try:
            line, col = err.position
        except:
            line = col = None
        return errors + [errcls(err.message, name, line, col)]
    except Exception as err:
        return errors + [errcls(err.message, name)]

    if mt in OEB_DOCS and root.nsmap.get(root.prefix, None) != XHTML_NS:
        errors.append(BadNamespace(name, root.nsmap.get(root.prefix, None)))

    return errors

class CSSError(BaseError):

    is_parsing_error = True

    def __init__(self, level, msg, name, line, col):
        self.level = level
        prefix = 'CSS: '
        BaseError.__init__(self, prefix + msg, name, line, col)
        if level == WARN:
            self.HELP = _('This CSS construct is not recognized. That means that it'
                          ' most likely will not work on reader devices. Consider'
                          ' replacing it with something else.')
        else:
            self.HELP = _('Some reader programs are very'
                          ' finicky about CSS stylesheets and will ignore the whole'
                          ' sheet if there is an error. These errors can often'
                          ' be fixed automatically, however, automatic fixing will'
                          ' typically remove unrecognized items, instead of correcting them.')
            self.INDIVIDUAL_FIX = _('Try to fix parsing errors in this stylesheet automatically')

    def __call__(self, container):
        root = container.parsed(self.name)
        container.dirty(self.name)
        if container.mime_map[self.name] in OEB_DOCS:
            for style in root.xpath('//*[local-name()="style"]'):
                if style.get('type', 'text/css') == 'text/css' and style.text and style.text.strip():
                    fix_style_tag(container, style)
            for elem in root.xpath('//*[@style]'):
                raw = elem.get('style')
                if raw:
                    elem.set('style', force_unicode(container.parse_css(raw, is_declaration=True).cssText, 'utf-8').replace('\n', ' '))
        return True

pos_pats = (re.compile(r'\[(\d+):(\d+)'), re.compile(r'(\d+), (\d+)\)'))

class ErrorHandler(object):

    ' Replacement logger to get useful error/warning info out of cssutils during parsing '

    def __init__(self, name):
        # may be disabled during setting of known valid items
        self.name = name
        self.errors = []

    def __noop(self, *args, **kwargs):
        pass
    info = debug = setLevel = getEffectiveLevel = addHandler = removeHandler = __noop

    def __handle(self, level, *args):
        msg = ' '.join(map(unicode, args))
        line = col = None
        for pat in pos_pats:
            m = pat.search(msg)
            if m is not None:
                line, col = int(m.group(1)), int(m.group(2))
        if msg and line is not None:
            # Ignore error messages with no line numbers as these are usually
            # summary messages for an underlying error with a line number
            if 'panose-1' in msg and 'unknown property name' in msg.lower():
                return  # panose-1 is allowed in CSS 2.1 and is generated by calibre
            self.errors.append(CSSError(level, msg, self.name, line, col))

    def error(self, *args):
        self.__handle(ERROR, *args)

    def warn(self, *args):
        self.__handle(WARN, *args)
    warning = warn

def check_css_parsing(name, raw, line_offset=0, is_declaration=False):
    log = ErrorHandler(name)
    parser = cssutils.CSSParser(fetcher=lambda x: (None, None), log=log)
    if is_declaration:
        parser.parseStyle(raw, validate=True)
    else:
        parser.parseString(raw, validate=True)
    for err in log.errors:
        err.line += line_offset
    return log.errors
