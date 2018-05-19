#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import re

from lxml.etree import XMLParser, fromstring, XMLSyntaxError
import cssutils

from calibre import force_unicode, human_readable, prepare_string_for_xml
from calibre.ebooks.chardet import replace_encoding_declarations, find_declared_encoding
from calibre.ebooks.html_entities import html5_entities
from calibre.ebooks.oeb.polish.pretty import pretty_script_or_style as fix_style_tag
from calibre.ebooks.oeb.polish.utils import PositionFinder, guess_type
from calibre.ebooks.oeb.polish.check.base import BaseError, WARN, ERROR, INFO
from calibre.ebooks.oeb.base import OEB_DOCS, XHTML_NS, urlquote, URL_SAFE, XHTML

HTML_ENTITTIES = frozenset(html5_entities)
XML_ENTITIES = {'lt', 'gt', 'amp', 'apos', 'quot'}
ALL_ENTITIES = HTML_ENTITTIES | XML_ENTITIES

replace_pat = re.compile('&(%s);' % '|'.join(re.escape(x) for x in sorted((HTML_ENTITTIES - XML_ENTITIES))))
mismatch_pat = re.compile(r'tag mismatch:.+?line (\d+).+?line \d+')


class EmptyFile(BaseError):

    HELP = _('This file is empty, it contains nothing, you should probably remove it.')
    INDIVIDUAL_FIX = _('Remove this file')

    def __init__(self, name):
        BaseError.__init__(self, _('The file %s is empty') % name, name)

    def __call__(self, container):
        container.remove_item(self.name)
        return True


class DecodeError(BaseError):

    is_parsing_error = True

    HELP = _('A decoding errors means that the contents of the file could not'
             ' be interpreted as text. This usually happens if the file has'
             ' an incorrect character encoding declaration or if the file is actually'
             ' a binary file, like an image or font that is mislabelled with'
             ' an incorrect media type in the OPF.')

    def __init__(self, name):
        BaseError.__init__(self, _('Parsing of %s failed, could not decode') % name, name)


class XMLParseError(BaseError):

    is_parsing_error = True

    HELP = _('A parsing error in an XML file means that the XML syntax in the file is incorrect.'
             ' Such a file will most probably not open in an e-book reader. These errors can '
             ' usually be fixed automatically, however, automatic fixing can sometimes '
             ' "do the wrong thing".')

    def __init__(self, msg, *args, **kwargs):
        msg = msg or ''
        BaseError.__init__(self, 'Parsing failed: ' + msg, *args, **kwargs)
        m = mismatch_pat.search(msg)
        if m is not None:
            self.has_multiple_locations = True
            self.all_locations = [(self.name, int(m.group(1)), None), (self.name, self.line, self.col)]


class HTMLParseError(XMLParseError):

    HELP = _('A parsing error in an HTML file means that the HTML syntax is incorrect.'
             ' Most readers will automatically ignore such errors, but they may result in '
             ' incorrect display of content. These errors can usually be fixed automatically,'
             ' however, automatic fixing can sometimes "do the wrong thing".')


class PrivateEntities(XMLParseError):

    HELP = _('This HTML file uses private entities.'
    ' These are not supported. You can try running "Fix HTML" from the Tools menu,'
    ' which will try to automatically resolve the private entities.')


class NamedEntities(BaseError):

    level = WARN
    INDIVIDUAL_FIX = _('Replace all named entities with their character equivalents in this book')
    HELP = _('Named entities are often only incompletely supported by various book reading software.'
             ' Therefore, it is best to not use them, replacing them with the actual characters they'
             ' represent. This can be done automatically.')

    def __init__(self, name):
        BaseError.__init__(self, _('Named entities present'), name)

    def __call__(self, container):
        changed = False
        from calibre.ebooks.oeb.polish.check.main import XML_TYPES
        check_types = XML_TYPES | OEB_DOCS
        for name, mt in container.mime_map.iteritems():
            if mt in check_types:
                raw = container.raw_data(name)
                nraw = replace_pat.sub(lambda m:html5_entities[m.group(1)], raw)
                if raw != nraw:
                    changed = True
                    with container.open(name, 'wb') as f:
                        f.write(nraw.encode('utf-8'))
        return changed


def make_filename_safe(name):
    from calibre.utils.filenames import ascii_filename

    def esc(n):
        return ''.join(x if x in URL_SAFE else '_' for x in n)
    return '/'.join(esc(ascii_filename(x)) for x in name.split('/'))


class EscapedName(BaseError):

    level = WARN

    def __init__(self, name):
        BaseError.__init__(self, _('Filename contains unsafe characters'), name)
        qname = urlquote(name)

        self.sname = make_filename_safe(name)
        self.HELP = _(
            'The filename {0} contains unsafe characters, that must be escaped, like'
            ' this {1}. This can cause problems with some e-book readers. To be'
            ' absolutely safe, use only the English alphabet [a-z], the numbers [0-9],'
            ' underscores and hyphens in your file names. While many other characters'
            ' are allowed, they may cause problems with some software.').format(name, qname)
        self.INDIVIDUAL_FIX = _(
            'Rename the file {0} to {1}').format(name, self.sname)

    def __call__(self, container):
        from calibre.ebooks.oeb.polish.replace import rename_files
        all_names = set(container.name_path_map)
        bn, ext = self.sname.rpartition('.')[0::2]
        c = 0
        while self.sname in all_names:
            c += 1
            self.sname = '%s_%d.%s' % (bn, c, ext)
        rename_files(container, {self.name:self.sname})
        return True


class TooLarge(BaseError):

    level = INFO
    MAX_SIZE = 260 *1024
    HELP = _('This HTML file is larger than %s. Too large HTML files can cause performance problems'
             ' on some e-book readers. Consider splitting this file into smaller sections.') % human_readable(MAX_SIZE)

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
            'This file has {0}. Its namespace must be {1}. Set the namespace by defining the xmlns'
            ' attribute on the <html> element, like this <html xmlns="{1}">').format(
                (_('incorrect namespace %s') % namespace) if namespace else _('no namespace'),
                XHTML_NS))

    def __call__(self, container):
        container.parsed(self.name)
        container.dirty(self.name)
        return True


class NonUTF8(BaseError):

    level = WARN
    INDIVIDUAL_FIX = _("Change this file's encoding to UTF-8")

    def __init__(self, name, enc):
        BaseError.__init__(self, _('Non UTF-8 encoding declaration'), name)
        self.HELP = _('This file has its encoding declared as %s. Some'
                      ' reader software cannot handle non-UTF8 encoded files.'
                      ' You should change the encoding to UTF-8.') % enc

    def __call__(self, container):
        raw = container.raw_data(self.name)
        if isinstance(raw, type('')):
            raw, changed = replace_encoding_declarations(raw)
            if changed:
                container.open(self.name, 'wb').write(raw.encode('utf-8'))
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


def check_encoding_declarations(name, container):
    errors = []
    enc = find_declared_encoding(container.raw_data(name))
    if enc is not None and enc.lower() != 'utf-8':
        errors.append(NonUTF8(name, enc))
    return errors


def check_for_private_entities(name, raw):
    if re.search(br'<!DOCTYPE\s+.+?<!ENTITY\s+.+?]>', raw, flags=re.DOTALL) is not None:
        return True


def check_xml_parsing(name, mt, raw):
    if not raw:
        return [EmptyFile(name)]
    if check_for_private_entities(name, raw):
        return [PrivateEntities(_('Private entities found'), name)]
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
    except UnicodeDecodeError:
        return errors + [DecodeError(name)]
    except XMLSyntaxError as err:
        try:
            line, col = err.position
        except:
            line = col = None
        return errors + [errcls(err.message, name, line, col)]
    except Exception as err:
        return errors + [errcls(err.message, name)]

    if mt in OEB_DOCS:
        if root.nsmap.get(root.prefix, None) != XHTML_NS:
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


class DuplicateId(BaseError):

    has_multiple_locations = True

    INDIVIDUAL_FIX = _(
        'Remove the duplicate ids from all but the first element')

    def __init__(self, name, eid, locs):
        BaseError.__init__(self, _('Duplicate id: %s') % eid, name)
        self.HELP = _(
            'The id {0} is present on more than one element in {1}. This is'
            ' not allowed. Remove the id from all but one of the elements').format(eid, name)
        self.all_locations = [(name, lnum, None) for lnum in sorted(locs)]
        self.duplicate_id = eid

    def __call__(self, container):
        elems = [e for e in container.parsed(self.name).xpath('//*[@id]') if e.get('id') == self.duplicate_id]
        for e in elems[1:]:
            e.attrib.pop('id')
        container.dirty(self.name)
        return True


class InvalidId(BaseError):

    level = WARN
    INDIVIDUAL_FIX = _(
        'Replace this id with a randomly generated valid id')

    def __init__(self, name, line, eid):
        BaseError.__init__(self, _('Invalid id: %s') % eid, name, line)
        self.HELP = _(
            'The id {0} is not a valid id. IDs must start with a letter ([A-Za-z]) and may be'
            ' followed by any number of letters, digits ([0-9]), hyphens ("-"), underscores ("_")'
            ', colons (":"), and periods ("."). This is to ensure maximum compatibility'
            ' with a wide range of devices.').format(eid)
        self.invalid_id = eid

    def __call__(self, container):
        from calibre.ebooks.oeb.base import uuid_id
        from calibre.ebooks.oeb.polish.replace import replace_ids
        newid = uuid_id()
        changed = False
        elems = (e for e in container.parsed(self.name).xpath('//*[@id]') if e.get('id') == self.invalid_id)
        for e in elems:
            e.set('id', newid)
            changed = True
            container.dirty(self.name)
        if changed:
            replace_ids(container, {self.name:{self.invalid_id:newid}})
        return changed


class BareTextInBody(BaseError):

    INDIVIDUAL_FIX = _('Wrap the bare text in a p tag')
    HELP = _('You cannot have bare text inside the body tag. The text must be placed inside some other tag, such as p or div')
    has_multiple_locations = True

    def __init__(self, name, lines):
        BaseError.__init__(self, _('Bare text in body tag'), name)
        self.all_locations = [(name, l, None) for l in sorted(lines)]

    def __call__(self, container):
        root = container.parsed(self.name)
        for body in root.xpath('//*[local-name() = "body"]'):
            children = tuple(body.iterchildren('*'))
            if body.text and body.text.strip():
                p = body.makeelement(XHTML('p'))
                p.text, body.text = body.text.strip(), '\n  '
                p.tail = '\n'
                if children:
                    p.tail += '  '
                body.insert(0, p)
            for child in children:
                if child.tail and child.tail.strip():
                    p = body.makeelement(XHTML('p'))
                    p.text, child.tail = child.tail.strip(), '\n  '
                    p.tail = '\n'
                    body.insert(body.index(child) + 1, p)
                    if child is not children[-1]:
                        p.tail += '  '
        container.dirty(self.name)
        return True


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
        try:
            parser.parseString(raw, validate=True)
        except UnicodeDecodeError:
            return [DecodeError(name)]
    for err in log.errors:
        err.line += line_offset
    return log.errors


def check_filenames(container):
    errors = []
    all_names = set(container.name_path_map) - container.names_that_must_not_be_changed
    for name in all_names:
        if urlquote(name) != name:
            errors.append(EscapedName(name))
    return errors


valid_id = re.compile(r'^[a-zA-Z][a-zA-Z0-9_:.-]*$')


def check_ids(container):
    errors = []
    mts = set(OEB_DOCS) | {guess_type('a.opf'), guess_type('a.ncx')}
    for name, mt in container.mime_map.iteritems():
        if mt in mts:
            root = container.parsed(name)
            seen_ids = {}
            dups = {}
            for elem in root.xpath('//*[@id]'):
                eid = elem.get('id')
                if eid in seen_ids:
                    if eid not in dups:
                        dups[eid] = [seen_ids[eid]]
                    dups[eid].append(elem.sourceline)
                else:
                    seen_ids[eid] = elem.sourceline
                if eid and valid_id.match(eid) is None:
                    errors.append(InvalidId(name, elem.sourceline, eid))
            errors.extend(DuplicateId(name, eid, locs) for eid, locs in dups.iteritems())
    return errors


def check_markup(container):
    errors = []
    for name, mt in container.mime_map.iteritems():
        if mt in OEB_DOCS:
            lines = []
            root = container.parsed(name)
            for body in root.xpath('//*[local-name()="body"]'):
                if body.text and body.text.strip():
                    lines.append(body.sourceline)
                for child in body.iterchildren('*'):
                    if child.tail and child.tail.strip():
                        lines.append(child.sourceline)
            if lines:
                errors.append(BareTextInBody(name, lines))
    return errors
