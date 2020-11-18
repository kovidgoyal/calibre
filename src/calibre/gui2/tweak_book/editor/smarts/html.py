#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import sys, re
from operator import itemgetter
from itertools import chain

from css_parser import parseStyle
from PyQt5.Qt import QTextEdit, Qt, QTextCursor

from calibre import prepare_string_for_xml, xml_entity_to_unicode
from calibre.ebooks.oeb.polish.container import OEB_DOCS
from calibre.ebooks.oeb.base import css_text
from calibre.gui2 import error_dialog
from calibre.gui2.tweak_book.editor.syntax.html import ATTR_NAME, ATTR_END, ATTR_START, ATTR_VALUE
from calibre.gui2.tweak_book import tprefs, current_container
from calibre.gui2.tweak_book.editor.smarts import NullSmarts
from calibre.gui2.tweak_book.editor.smarts.utils import (
    no_modifiers, get_leading_whitespace_on_block, get_text_before_cursor,
    get_text_after_cursor, smart_home, smart_backspace, smart_tab, expand_tabs)
from calibre.utils.icu import utf16_length
from polyglot.builtins import unicode_type

get_offset = itemgetter(0)
PARAGRAPH_SEPARATOR = '\u2029'
DEFAULT_LINK_TEMPLATE = '<a href="_TARGET_">_TEXT_</a>'


class Tag(object):

    def __init__(self, start_block, tag_start, end_block, tag_end, self_closing=False):
        self.start_block, self.end_block = start_block, end_block
        self.start_offset, self.end_offset = tag_start.offset, tag_end.offset
        tag = tag_start.name
        if tag_start.prefix:
            tag = tag_start.prefix + ':' + tag
        self.name = tag
        self.self_closing = self_closing

    def __repr__(self):
        return '<%s start_block=%s start_offset=%s end_block=%s end_offset=%s self_closing=%s>' % (
            self.name, self.start_block.blockNumber(), self.start_offset, self.end_block.blockNumber(), self.end_offset, self.self_closing)
    __str__ = __repr__


def next_tag_boundary(block, offset, forward=True, max_lines=10000):
    while block.isValid() and max_lines > 0:
        ud = block.userData()
        if ud is not None:
            tags = sorted(ud.tags, key=get_offset, reverse=not forward)
            for boundary in tags:
                if forward and boundary.offset > offset:
                    return block, boundary
                if not forward and boundary.offset < offset:
                    return block, boundary
        block = block.next() if forward else block.previous()
        offset = -1 if forward else sys.maxsize
        max_lines -= 1
    return None, None


def next_attr_boundary(block, offset, forward=True):
    while block.isValid():
        ud = block.userData()
        if ud is not None:
            attributes = sorted(ud.attributes, key=get_offset, reverse=not forward)
            for boundary in attributes:
                if forward and boundary.offset >= offset:
                    return block, boundary
                if not forward and boundary.offset <= offset:
                    return block, boundary
        block = block.next() if forward else block.previous()
        offset = -1 if forward else sys.maxsize
    return None, None


def find_closest_containing_tag(block, offset, max_tags=sys.maxsize):
    ''' Find the closest containing tag. To find it, we search for the first
    opening tag that does not have a matching closing tag before the specified
    position. Search through at most max_tags. '''
    prev_tag_boundary = lambda b, o: next_tag_boundary(b, o, forward=False)

    block, boundary = prev_tag_boundary(block, offset)
    if block is None:
        return None
    if boundary.is_start:
        # We are inside a tag already
        if boundary.closing:
            return find_closest_containing_tag(block, boundary.offset)
        eblock, eboundary = next_tag_boundary(block, boundary.offset)
        if eblock is None or eboundary is None or eboundary.is_start:
            return None
        if eboundary.self_closing:
            return Tag(block, boundary, eblock, eboundary, self_closing=True)
        return find_closest_containing_tag(eblock, eboundary.offset + 1)
    stack = []
    block, tag_end = block, boundary
    while block is not None and max_tags > 0:
        sblock, tag_start = prev_tag_boundary(block, tag_end.offset)
        if sblock is None or not tag_start.is_start:
            break
        if tag_start.closing:  # A closing tag of the form </a>
            stack.append((tag_start.prefix, tag_start.name))
        elif tag_end.self_closing:  # A self closing tag of the form <a/>
            pass  # Ignore it
        else:  # An opening tag, hurray
            try:
                prefix, name = stack.pop()
            except IndexError:
                prefix = name = None
            if (prefix, name) != (tag_start.prefix, tag_start.name):
                # Either we have an unbalanced opening tag or a syntax error, in
                # either case terminate
                return Tag(sblock, tag_start, block, tag_end)
        block, tag_end = prev_tag_boundary(sblock, tag_start.offset)
        max_tags -= 1
    return None  # Could not find a containing tag


def find_tag_definition(block, offset):
    ''' Return the <tag | > definition, if any that (block, offset) is inside. '''
    block, boundary = next_tag_boundary(block, offset, forward=False)
    if not boundary or not boundary.is_start:
        return None, False
    tag_start = boundary
    closing = tag_start.closing
    tag = tag_start.name
    if tag_start.prefix:
        tag = tag_start.prefix + ':' + tag
    return tag, closing


def find_containing_attribute(block, offset):
    block, boundary = next_attr_boundary(block, offset, forward=False)
    if block is None:
        return None
    if boundary.type is ATTR_NAME or boundary.data is ATTR_END:
        return None  # offset is not inside an attribute value
    block, boundary = next_attr_boundary(block, boundary.offset - 1, forward=False)
    if block is not None and boundary.type == ATTR_NAME:
        return boundary.data
    return None


def find_attribute_in_tag(block, offset, attr_name):
    ' Return the start of the attribute value as block, offset or None, None if attribute not found '
    end_block, boundary = next_tag_boundary(block, offset)
    if boundary.is_start:
        return None, None
    end_offset = boundary.offset
    end_pos = (end_block.blockNumber(), end_offset)
    current_block, current_offset = block, offset
    found_attr = False
    while True:
        current_block, boundary = next_attr_boundary(current_block, current_offset)
        if current_block is None or (current_block.blockNumber(), boundary.offset) > end_pos:
            return None, None
        current_offset = boundary.offset
        if found_attr:
            if boundary.type is not ATTR_VALUE or boundary.data is not ATTR_START:
                return None, None
            return current_block, current_offset
        else:
            if boundary.type is ATTR_NAME and boundary.data.lower() == attr_name.lower():
                found_attr = True
            current_offset += 1


def find_end_of_attribute(block, offset):
    ' Find the end of an attribute that occurs somewhere after the position specified by (block, offset) '
    block, boundary = next_attr_boundary(block, offset)
    if block is None or boundary is None:
        return None, None
    if boundary.type is not ATTR_VALUE or boundary.data is not ATTR_END:
        return None, None
    return block, boundary.offset


def find_closing_tag(tag, max_tags=sys.maxsize):
    ''' Find the closing tag corresponding to the specified tag. To find it we
    search for the first closing tag after the specified tag that does not
    match a previous opening tag. Search through at most max_tags. '''
    if tag.self_closing:
        return None
    stack = []
    block, offset = tag.end_block, tag.end_offset
    while block.isValid() and max_tags > 0:
        block, tag_start = next_tag_boundary(block, offset)
        if block is None or not tag_start.is_start:
            break
        endblock, tag_end = next_tag_boundary(block, tag_start.offset)
        if endblock is None or tag_end.is_start:
            break
        if tag_start.closing:
            try:
                prefix, name = stack.pop()
            except IndexError:
                prefix = name = None
            if (prefix, name) != (tag_start.prefix, tag_start.name):
                return Tag(block, tag_start, endblock, tag_end)
        elif tag_end.self_closing:
            pass
        else:
            stack.append((tag_start.prefix, tag_start.name))
        block, offset = endblock, tag_end.offset
        max_tags -= 1
    return None


def select_tag(cursor, tag):
    cursor.setPosition(tag.start_block.position() + tag.start_offset)
    cursor.setPosition(tag.end_block.position() + tag.end_offset + 1, cursor.KeepAnchor)
    return unicode_type(cursor.selectedText()).replace(PARAGRAPH_SEPARATOR, '\n').rstrip('\0')


def rename_tag(cursor, opening_tag, closing_tag, new_name, insert=False):
    cursor.beginEditBlock()
    text = select_tag(cursor, closing_tag)
    if insert:
        text = '</%s>%s' % (new_name, text)
    else:
        text = re.sub(r'^<\s*/\s*[a-zA-Z0-9]+', '</%s' % new_name, text)
    cursor.insertText(text)
    text = select_tag(cursor, opening_tag)
    if insert:
        text += '<%s>' % new_name
    else:
        text = re.sub(r'^<\s*[a-zA-Z0-9]+', '<%s' % new_name, text)
    cursor.insertText(text)
    cursor.endEditBlock()


def ensure_not_within_tag_definition(cursor, forward=True):
    ''' Ensure the cursor is not inside a tag definition <>. Returns True iff the cursor was moved. '''
    block, offset = cursor.block(), cursor.positionInBlock()
    b, boundary = next_tag_boundary(block, offset, forward=False)
    if b is None:
        return False
    if boundary.is_start:
        # We are inside a tag
        if forward:
            block, boundary = next_tag_boundary(block, offset)
            if block is not None:
                cursor.setPosition(block.position() + boundary.offset + 1)
                return True
        else:
            cursor.setPosition(b.position() + boundary.offset)
            return True

    return False


BLOCK_TAG_NAMES = frozenset((
    'address', 'article', 'aside', 'blockquote', 'center', 'dir', 'fieldset',
    'isindex', 'menu', 'noframes', 'hgroup', 'noscript', 'pre', 'section',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'header', 'p', 'div', 'dd', 'dl', 'ul',
    'ol', 'li', 'body', 'td', 'th'))


def find_closest_containing_block_tag(block, offset, block_tag_names=BLOCK_TAG_NAMES):
    while True:
        tag = find_closest_containing_tag(block, offset)
        if tag is None:
            break
        if tag.name in block_tag_names:
            return tag
        block, offset = tag.start_block, tag.start_offset


def set_style_property(tag, property_name, value, editor):
    '''
    Set a style property, i.e. a CSS property inside the style attribute of the tag.
    Any existing style attribute is updated or a new attribute is inserted.
    '''
    block, offset = find_attribute_in_tag(tag.start_block, tag.start_offset + 1, 'style')
    c = editor.textCursor()

    def css(d):
        return css_text(d).replace('\n', ' ')
    if block is None or offset is None:
        d = parseStyle('')
        d.setProperty(property_name, value)
        c.setPosition(tag.end_block.position() + tag.end_offset)
        c.insertText(' style="%s"' % css(d))
    else:
        c.setPosition(block.position() + offset - 1)
        end_block, end_offset = find_end_of_attribute(block, offset + 1)
        if end_block is None:
            return error_dialog(editor, _('Invalid markup'), _(
                'The current block tag has an existing unclosed style attribute. Run the Fix HTML'
                ' tool first.'), show=True)
        c.setPosition(end_block.position() + end_offset, c.KeepAnchor)
        d = parseStyle(editor.selected_text_from_cursor(c)[1:-1])
        d.setProperty(property_name, value)
        c.insertText('"%s"' % css(d))


entity_pat = re.compile(r'&(#{0,1}[a-zA-Z0-9]{1,8});$')


class Smarts(NullSmarts):

    def __init__(self, *args, **kwargs):
        if not hasattr(Smarts, 'regexps_compiled'):
            Smarts.regexps_compiled = True
            Smarts.tag_pat = re.compile(r'<[^>]+>')
            Smarts.closing_tag_pat = re.compile(r'<\s*/[^>]+>')
            Smarts.closing_pat = re.compile(r'<\s*/')
            Smarts.self_closing_pat = re.compile(r'/\s*>')
            Smarts.complete_attr_pat = re.compile(r'''([a-zA-Z0-9_-]+)\s*=\s*(?:'([^']*)|"([^"]*))$''')
        NullSmarts.__init__(self, *args, **kwargs)
        self.last_matched_tag = self.last_matched_closing_tag = None

    def get_extra_selections(self, editor):
        ans = []

        def add_tag(tag):
            a = QTextEdit.ExtraSelection()
            a.cursor, a.format = editor.textCursor(), editor.match_paren_format
            a.cursor.setPosition(tag.start_block.position()), a.cursor.movePosition(a.cursor.EndOfBlock, a.cursor.KeepAnchor)
            text = unicode_type(a.cursor.selectedText())
            start_pos = utf16_length(text[:tag.start_offset])
            a.cursor.setPosition(tag.end_block.position()), a.cursor.movePosition(a.cursor.EndOfBlock, a.cursor.KeepAnchor)
            text = unicode_type(a.cursor.selectedText())
            end_pos = utf16_length(text[:tag.end_offset + 1])
            a.cursor.setPosition(tag.start_block.position() + start_pos)
            a.cursor.setPosition(tag.end_block.position() + end_pos, a.cursor.KeepAnchor)
            ans.append(a)

        c = editor.textCursor()
        block, offset = c.block(), c.positionInBlock()
        tag = self.last_matched_tag = find_closest_containing_tag(block, offset, max_tags=2000)
        self.last_matched_closing_tag = None
        if tag is not None:
            add_tag(tag)
            tag = self.last_matched_closing_tag = find_closing_tag(tag, max_tags=4000)
            if tag is not None:
                add_tag(tag)
        return ans

    def jump_to_enclosing_tag(self, editor, start=True):
        editor.highlighter.join()
        tag = self.last_matched_tag if start else self.last_matched_closing_tag
        if tag is None:
            return False
        c = editor.textCursor()
        c.setPosition(tag.start_block.position() + tag.start_offset + (1 if start else 2))
        editor.setTextCursor(c)
        return True

    def select_tag_contents(self, editor):
        editor.highlighter.join()
        start = self.last_matched_tag
        end = self.last_matched_closing_tag
        if start is None or end is None:
            return False
        c = editor.textCursor()
        c.setPosition(start.start_block.position() + start.end_offset + 1)
        c.setPosition(end.start_block.position() + end.start_offset, c.KeepAnchor)
        editor.setTextCursor(c)
        return True

    def remove_tag(self, editor):
        editor.highlighter.join()
        if not self.last_matched_closing_tag and not self.last_matched_tag:
            return
        c = editor.textCursor()
        c.beginEditBlock()

        def erase_tag(tag):
            c.setPosition(tag.start_block.position() + tag.start_offset)
            c.setPosition(tag.end_block.position() + tag.end_offset + 1, c.KeepAnchor)
            c.removeSelectedText()

        if self.last_matched_closing_tag:
            erase_tag(self.last_matched_closing_tag)
        if self.last_matched_tag:
            erase_tag(self.last_matched_tag)
        c.endEditBlock()
        self.last_matched_tag = self.last_matched_closing_tag = None

    def rename_block_tag(self, editor, new_name):
        editor.highlighter.join()
        c = editor.textCursor()
        block, offset = c.block(), c.positionInBlock()
        tag = find_closest_containing_block_tag(block, offset)

        if tag is not None:
            closing_tag = find_closing_tag(tag)
            if closing_tag is None:
                return error_dialog(editor, _('Invalid HTML'), _(
                    'There is an unclosed %s tag. You should run the Fix HTML tool'
                    ' before trying to rename tags.') % tag.name, show=True)
            rename_tag(c, tag, closing_tag, new_name, insert=tag.name in {'body', 'td', 'th', 'li'})
        else:
            return error_dialog(editor, _('No found'), _(
                'No suitable block level tag was found to rename'), show=True)

    def get_smart_selection(self, editor, update=True):
        editor.highlighter.join()
        cursor = editor.textCursor()
        if not cursor.hasSelection():
            return ''
        left = min(cursor.anchor(), cursor.position())
        right = max(cursor.anchor(), cursor.position())

        cursor.setPosition(left)
        ensure_not_within_tag_definition(cursor)
        left = cursor.position()

        cursor.setPosition(right)
        ensure_not_within_tag_definition(cursor, forward=False)
        right = cursor.position()

        cursor.setPosition(left), cursor.setPosition(right, cursor.KeepAnchor)
        if update:
            editor.setTextCursor(cursor)
        return editor.selected_text_from_cursor(cursor)

    def insert_hyperlink(self, editor, target, text, template=None):
        template = template or DEFAULT_LINK_TEMPLATE
        template = template.replace('_TARGET_', prepare_string_for_xml(target, True))
        offset = template.find('_TEXT_')
        template = template.replace('_TEXT_', text or '')
        editor.highlighter.join()
        c = editor.textCursor()
        if c.hasSelection():
            c.insertText('')  # delete any existing selected text
        ensure_not_within_tag_definition(c)
        p = c.position() + offset
        c.insertText(template)
        c.setPosition(p)  # ensure cursor is positioned inside the newly created tag
        editor.setTextCursor(c)

    def insert_tag(self, editor, name):
        editor.highlighter.join()
        name = name.lstrip()
        text = self.get_smart_selection(editor, update=True)
        c = editor.textCursor()
        pos = min(c.position(), c.anchor())
        m = re.match(r'[a-zA-Z0-9:-]+', name)
        cname = name if m is None else m.group()
        c.insertText('<{0}>{1}</{2}>'.format(name, text, cname))
        c.setPosition(pos + 2 + len(name))
        editor.setTextCursor(c)

    def verify_for_spellcheck(self, cursor, highlighter):
        # Return True iff the cursor is in a location where spelling is
        # checked (inside a tag or inside a checked attribute)
        highlighter.join()
        block = cursor.block()
        start_pos = cursor.anchor() - block.position()
        end_pos = cursor.position() - block.position()
        start_tag, closing = find_tag_definition(block, start_pos)
        if closing:
            return False
        end_tag, closing = find_tag_definition(block, end_pos)
        if closing:
            return False
        if start_tag is None and end_tag is None:
            # We are in normal text, check that the containing tag is
            # allowed for spell checking.
            tag = find_closest_containing_tag(block, start_pos)
            if tag is not None and highlighter.tag_ok_for_spell(tag.name.split(':')[-1]):
                return True
        if start_tag != end_tag:
            return False

        # Now we check if we are in an allowed attribute
        sa = find_containing_attribute(block, start_pos)
        ea = find_containing_attribute(block, end_pos)

        if sa == ea and sa in highlighter.spell_attributes:
            return True

        return False

    def cursor_position_with_sourceline(self, cursor, for_position_sync=True, use_matched_tag=True):
        ''' Return the tag just before the current cursor as a source line
        number and a list of tags defined on that line up to and including the
        containing tag. If ``for_position_sync`` is False then the tag
        *containing* the cursor is returned instead of the tag just before the
        cursor. Note that finding the containing tag is expensive, so
        use with care. As an optimization, the last tag matched by
        get_extra_selections is used, unless use_matched_tag is False. '''
        block, offset = cursor.block(), cursor.positionInBlock()
        if for_position_sync:
            nblock, boundary = next_tag_boundary(block, offset, forward=False)
            if boundary is None:
                return None, None
            if boundary.is_start:
                # We are inside a tag, use this tag
                start_block, start_offset = nblock, boundary.offset
            else:
                start_block = None
                while start_block is None and block.isValid():
                    ud = block.userData()
                    if ud is not None:
                        for boundary in reversed(ud.tags):
                            if boundary.is_start and not boundary.closing and boundary.offset <= offset:
                                start_block, start_offset = block, boundary.offset
                                break
                    block, offset = block.previous(), sys.maxsize
            end_block = None
            if start_block is not None:
                end_block, boundary = next_tag_boundary(start_block, start_offset)
                if boundary is None or boundary.is_start:
                    return None, None
        else:
            tag = None
            if use_matched_tag:
                tag = self.last_matched_tag
            if tag is None:
                tag = find_closest_containing_tag(block, offset, max_tags=2000)
            if tag is None:
                return None, None
            start_block, start_offset, end_block = tag.start_block, tag.start_offset, tag.end_block
        if start_block is None or end_block is None:
            return None, None
        sourceline = end_block.blockNumber() + 1  # blockNumber() is zero based
        ud = start_block.userData()
        if ud is None:
            return None, None
        tags = [t.name for t in ud.tags if (t.is_start and not t.closing and t.offset <= start_offset)]
        if start_block.blockNumber() != end_block.blockNumber():
            # Multiline opening tag, it must be the first tag on the line with the closing >
            del tags[:-1]
        return sourceline, tags

    def goto_sourceline(self, editor, sourceline, tags, attribute=None):
        ''' Move the cursor to the tag identified by sourceline and tags (a
        list of tags names on the specified line). If attribute is specified
        the cursor will be placed at the start of the attribute value. '''
        found_tag = False
        if sourceline is None:
            return found_tag
        block = editor.document().findBlockByNumber(sourceline - 1)  # blockNumber() is zero based
        if not block.isValid():
            return found_tag
        editor.highlighter.join()
        c = editor.textCursor()
        ud = block.userData()
        all_tags = [] if ud is None else [t for t in ud.tags if (t.is_start and not t.closing)]
        tag_names = [t.name for t in all_tags]
        if all_tags and tag_names[:len(tags)] == tags:
            c.setPosition(block.position() + all_tags[len(tags)-1].offset)
            found_tag = True
        else:
            c.setPosition(block.position())
        if found_tag and attribute is not None:
            start_offset = c.position() - block.position()
            nblock, offset = find_attribute_in_tag(block, start_offset, attribute)
            if nblock is not None:
                c.setPosition(nblock.position() + offset)
        editor.setTextCursor(c)
        return found_tag

    def get_inner_HTML(self, editor):
        ''' Select the inner HTML of the current tag. Return a cursor with the
        inner HTML selected or None. '''
        editor.highlighter.join()
        c = editor.textCursor()
        block = c.block()
        offset = c.position() - block.position()
        nblock, boundary = next_tag_boundary(block, offset)
        if boundary.is_start:
            # We are within the contents of a tag already
            tag = find_closest_containing_tag(block, offset)
        else:
            # We are inside a tag definition < | >
            if boundary.self_closing:
                return None  # self closing tags have no inner html
            tag = find_closest_containing_tag(nblock, boundary.offset + 1)
        if tag is None:
            return None
        ctag = find_closing_tag(tag)
        if ctag is None:
            return None
        c.setPosition(tag.end_block.position() + tag.end_offset + 1)
        c.setPosition(ctag.start_block.position() + ctag.start_offset, c.KeepAnchor)
        return c

    def set_text_alignment(self, editor, value):
        ''' Set the text-align property on the current block tag(s) '''
        editor.highlighter.join()
        block_tag_names = BLOCK_TAG_NAMES - {'body'}  # ignore body since setting text-align globally on body is almost never what is wanted
        tags = []
        c = editor.textCursor()
        if c.hasSelection():
            start, end = min(c.anchor(), c.position()), max(c.anchor(), c.position())
            c.setPosition(start)
            block = c.block()
            while block.isValid() and block.position() < end:
                ud = block.userData()
                if ud is not None:
                    for tb in ud.tags:
                        if tb.is_start and not tb.closing and tb.name.lower() in block_tag_names:
                            nblock, boundary = next_tag_boundary(block, tb.offset)
                            if boundary is not None and not boundary.is_start and not boundary.self_closing:
                                tags.append(Tag(block, tb, nblock, boundary))
                block = block.next()
        if not tags:
            c = editor.textCursor()
            block, offset = c.block(), c.positionInBlock()
            tag = find_closest_containing_block_tag(block, offset, block_tag_names)
            if tag is None:
                return error_dialog(editor, _('Not in a block tag'), _(
                    'Cannot change text alignment as the cursor is not inside a block level tag, such as a &lt;p&gt; or &lt;div&gt; tag.'), show=True)
            tags = [tag]
        for tag in reversed(tags):
            set_style_property(tag, 'text-align', value, editor)

    def handle_key_press(self, ev, editor):
        ev_text = ev.text()
        key = ev.key()
        is_xml = editor.syntax == 'xml'

        if tprefs['replace_entities_as_typed'] and (
                ';' in ev_text or
                (key == Qt.Key_Semicolon and no_modifiers(ev, Qt.ControlModifier, Qt.AltModifier))
        ):
            self.replace_possible_entity(editor)
            return True

        if key in (Qt.Key_Enter, Qt.Key_Return) and no_modifiers(ev, Qt.ControlModifier, Qt.AltModifier):
            ls = get_leading_whitespace_on_block(editor)
            if ls == ' ':
                ls = ''  # Do not consider a single leading space as indentation
            if is_xml:
                count = 0
                for m in self.tag_pat.finditer(get_text_before_cursor(editor)[1]):
                    text = m.group()
                    if self.closing_pat.search(text) is not None:
                        count -= 1
                    elif self.self_closing_pat.search(text) is None:
                        count += 1
                if self.closing_tag_pat.match(get_text_after_cursor(editor)[1].lstrip()):
                    count -= 1
                if count > 0:
                    ls += editor.tw * ' '
            editor.textCursor().insertText('\n' + ls)
            return True

        if key == Qt.Key_Slash:
            cursor, text = get_text_before_cursor(editor)
            if not text.rstrip().endswith('<'):
                return False
            text = expand_tabs(text.rstrip()[:-1], editor.tw)
            pls = get_leading_whitespace_on_block(editor, previous=True)
            if is_xml and not text.lstrip() and len(text) > 1 and len(text) >= len(pls):
                # Auto-dedent
                text = text[:-editor.tw] + '</'
                cursor.insertText(text)
                editor.setTextCursor(cursor)
                self.auto_close_tag(editor)
                return True
            if self.auto_close_tag(editor):
                return True

        if key == Qt.Key_Home and smart_home(editor, ev):
            return True

        if key == Qt.Key_Tab and smart_tab(editor, ev):
            return True

        if key == Qt.Key_Backspace and smart_backspace(editor, ev):
            return True

        if key in (Qt.Key_BraceLeft, Qt.Key_BraceRight):
            mods = ev.modifiers()
            if int(mods & Qt.ControlModifier):
                if self.jump_to_enclosing_tag(editor, key == Qt.Key_BraceLeft):
                    return True
        if key == Qt.Key_T and int(ev.modifiers() & (Qt.ControlModifier | Qt.AltModifier)):
            return self.select_tag_contents(editor)

        return False

    def replace_possible_entity(self, editor):
        c = editor.textCursor()
        c.insertText(';')
        c.setPosition(c.position() - min(c.positionInBlock(), 10), c.KeepAnchor)
        text = editor.selected_text_from_cursor(c)
        m = entity_pat.search(text)
        if m is not None:
            ent = m.group()
            repl = xml_entity_to_unicode(m)
            if repl != ent:
                c.setPosition(c.position() + m.start(), c.KeepAnchor)
                c.insertText(repl)
                editor.setTextCursor(c)

    def auto_close_tag(self, editor):
        if not tprefs['auto_close_tags']:
            return False

        def check_if_in_tag(block, offset=0):
            if block.isValid():
                text = block.text()
                close_pos = text.find('>', offset)
                open_pos = text.find('<', offset)
                if (close_pos > -1 and open_pos == -1) or (close_pos < open_pos):
                    return True
            return False

        editor.highlighter.join()
        c = editor.textCursor()
        block, offset = c.block(), c.positionInBlock()
        if check_if_in_tag(block, offset) or check_if_in_tag(block.next()):
            return False
        tag = find_closest_containing_tag(block, offset - 1, max_tags=4000)
        if tag is None:
            return False
        c.insertText('/%s>' % tag.name)
        editor.setTextCursor(c)
        return True

    def get_completion_data(self, editor, ev=None):
        c = editor.textCursor()
        block, offset = c.block(), c.positionInBlock()
        oblock, boundary = next_tag_boundary(block, offset, forward=False, max_lines=5)
        if boundary is None or not boundary.is_start or boundary.closing:
            # Not inside a opening tag definition
            return
        tagname = boundary.name.lower()
        startpos = oblock.position() + boundary.offset
        c.setPosition(c.position()), c.setPosition(startpos, c.KeepAnchor)
        text = c.selectedText()
        m = self.complete_attr_pat.search(text)
        if m is None:
            return
        attr = m.group(1).lower().split(':')[-1]
        doc_name = editor.completion_doc_name
        if doc_name and attr in {'href', 'src'}:
            # A link
            query = m.group(2) or m.group(3) or ''
            c = current_container()
            names_type = {'a':'text_link', 'img':'image', 'image':'image', 'link':'stylesheet'}.get(tagname)
            idx = query.find('#')
            if idx > -1 and names_type in (None, 'text_link'):
                href, query = query[:idx], query[idx+1:]
                name = c.href_to_name(href) if href else doc_name
                if c.mime_map.get(name) in OEB_DOCS:
                    return 'complete_anchor', name, query

            return 'complete_names', (names_type, doc_name, c.root), query

    def find_text(self, pat, cursor, reverse):
        from calibre.gui2.tweak_book.text_search import find_text_in_chunks
        chunks = []

        cstart = min(cursor.position(), cursor.anchor())
        cend = max(cursor.position(), cursor.anchor())
        if reverse:
            cend -= 1
        c = QTextCursor(cursor)
        c.setPosition(cstart)
        block = c.block()
        in_text = find_tag_definition(block, 0)[0] is None
        if in_text:
            # Check if we are in comment/PI/etc.
            pb = block.previous()
            while pb.isValid():
                boundaries = pb.userData().non_tag_structures
                if boundaries:
                    if boundaries[-1].is_start:
                        in_text = False
                    break
                pb = pb.previous()

        def append(text, start):
            text = text.replace(PARAGRAPH_SEPARATOR, '\n')
            after = start + len(text)
            if start <= cend and cstart < after:
                extra = after - (cend + 1)
                if extra > 0:
                    text = text[:-extra]
                extra = cstart - start
                if extra > 0:
                    text = text[extra:]
                chunks.append((text, start + max(extra, 0)))

        while block.isValid() and block.position() <= cend:
            ud = block.userData()
            boundaries = sorted(chain(ud.tags, ud.non_tag_structures), key=get_offset)
            if not boundaries:
                # Add the whole line
                if in_text:
                    text = block.text() + '\n'
                    append(text, block.position())
            else:
                start = block.position()
                c.setPosition(start)
                for b in boundaries:
                    if in_text:
                        c.setPosition(start + b.offset, c.KeepAnchor)
                        if c.hasSelection():
                            append(c.selectedText(), c.anchor())
                    in_text = not b.is_start
                    c.setPosition(start + b.offset + 1)
                if in_text:
                    # Add remaining text in block
                    c.setPosition(block.position() + boundaries[-1].offset + 1)
                    c.movePosition(c.EndOfBlock, c.KeepAnchor)
                    if c.hasSelection():
                        append(c.selectedText() + '\n', c.anchor())
            block = block.next()
        s, e = find_text_in_chunks(pat, chunks)
        return s != -1 and e != -1, s, e


if __name__ == '__main__':  # {{{
    from calibre.gui2.tweak_book.editor.widget import launch_editor
    if sys.argv[-1].endswith('.html'):
        raw = lopen(sys.argv[-1], 'rb').read().decode('utf-8')
    else:
        raw = '''\
<!DOCTYPE html>
<html xml:lang="en" lang="en">
<!--
-->
    <head>
        <meta charset="utf-8" />
        <title>A title with a tag <span> in it, the tag is treated as normal text</title>
        <style type="text/css">
            body {
                  color: green;
                  font-size: 12pt;
            }
        </style>
        <style type="text/css">p.small { font-size: x-small; color:gray }</style>
    </head id="invalid attribute on closing tag">
    <body lang="en_IN"><p:
        <!-- The start of the actual body text -->
        <h1 lang="en_US">A heading that should appear in bold, with an <i>italic</i> word</h1>
        <p>Some text with inline formatting, that is syntax highlighted. A <b>bold</b> word, and an <em>italic</em> word. \
<i>Some italic text with a <b>bold-italic</b> word in </i>the middle.</p>
        <!-- Let's see what exotic constructs like namespace prefixes and empty attributes look like -->
        <svg:svg xmlns:svg="http://whatever" />
        <input disabled><input disabled /><span attr=<></span>
        <!-- Non-breaking spaces are rendered differently from normal spaces, so that they stand out -->
        <p>Some\xa0words\xa0separated\xa0by\xa0non\u2011breaking\xa0spaces and non\u2011breaking hyphens.</p>
        <p>Some non-BMP unicode text:\U0001f431\U0001f431\U0001f431</p>
    </body>
</html>
'''

    def callback(ed):
        import regex
        ed.find_text(regex.compile('A bold word'))
    launch_editor(raw, path_is_raw=True, syntax='html', callback=callback)
# }}}
