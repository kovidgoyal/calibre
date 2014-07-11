#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import sys, re
from operator import itemgetter

from cssutils import parseStyle
from PyQt4.Qt import QTextEdit

from calibre import prepare_string_for_xml
from calibre.gui2 import error_dialog
from calibre.gui2.tweak_book.editor.syntax.html import ATTR_NAME, ATTR_END, ATTR_START, ATTR_VALUE
from calibre.utils.icu import utf16_length
from calibre.gui2.tweak_book.editor.smart import NullSmarts

get_offset = itemgetter(0)
PARAGRAPH_SEPARATOR = '\u2029'

class Tag(object):

    def __init__(self, start_block, tag_start, end_block, tag_end, self_closing=False):
        self.start_block, self.end_block = start_block, end_block
        self.start_offset, self.end_offset = tag_start.offset, tag_end.offset
        tag = tag_start.name
        if tag_start.prefix:
            tag = tag_start.prefix + ':' + tag
        self.name = tag
        self.self_closing = self_closing

def next_tag_boundary(block, offset, forward=True):
    while block.isValid():
        ud = block.userData()
        if ud is not None:
            tags = sorted(ud.tags, key=get_offset, reverse=not forward)
            for boundary in tags:
                if forward and boundary.offset > offset:
                    return block, boundary
                if not forward and boundary.offset < offset:
                    return block, boundary
        block = block.next() if forward else block.previous()
        offset = -1 if forward else sys.maxint
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
        offset = -1 if forward else sys.maxint
    return None, None

def find_closest_containing_tag(block, offset, max_tags=sys.maxint):
    ''' Find the closest containing tag. To find it, we search for the first
    opening tag that does not have a matching closing tag before the specified
    position. Search through at most max_tags. '''
    prev_tag_boundary = lambda b, o: next_tag_boundary(b, o, forward=False)

    block, boundary = prev_tag_boundary(block, offset)
    if block is None:
        return None
    if boundary.is_start:
        # We are inside a tag, therefore the containing tag is the parent tag of
        # this tag
        return find_closest_containing_tag(block, boundary.offset)
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
    if not boundary.is_start:
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

def find_closing_tag(tag, max_tags=sys.maxint):
    ''' Find the closing tag corresponding to the specified tag. To find it we
    search for the first closing tag after the specified tag that does not
    match a previous opening tag. Search through at most max_tags. '''

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
    return unicode(cursor.selectedText()).replace(PARAGRAPH_SEPARATOR, '\n').rstrip('\0')

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
        return d.cssText.replace('\n', ' ')
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

class HTMLSmarts(NullSmarts):

    def get_extra_selections(self, editor):
        ans = []

        def add_tag(tag):
            a = QTextEdit.ExtraSelection()
            a.cursor, a.format = editor.textCursor(), editor.match_paren_format
            a.cursor.setPosition(tag.start_block.position()), a.cursor.movePosition(a.cursor.EndOfBlock, a.cursor.KeepAnchor)
            text = unicode(a.cursor.selectedText())
            start_pos = utf16_length(text[:tag.start_offset])
            a.cursor.setPosition(tag.end_block.position()), a.cursor.movePosition(a.cursor.EndOfBlock, a.cursor.KeepAnchor)
            text = unicode(a.cursor.selectedText())
            end_pos = utf16_length(text[:tag.end_offset + 1])
            a.cursor.setPosition(tag.start_block.position() + start_pos)
            a.cursor.setPosition(tag.end_block.position() + end_pos, a.cursor.KeepAnchor)
            ans.append(a)

        c = editor.textCursor()
        block, offset = c.block(), c.positionInBlock()
        tag = find_closest_containing_tag(block, offset, max_tags=2000)
        if tag is not None:
            add_tag(tag)
            tag = find_closing_tag(tag, max_tags=4000)
            if tag is not None:
                add_tag(tag)
        return ans

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

    def insert_hyperlink(self, editor, target, text):
        editor.highlighter.join()
        c = editor.textCursor()
        if c.hasSelection():
            c.insertText('')  # delete any existing selected text
        ensure_not_within_tag_definition(c)
        c.insertText('<a href="%s">' % prepare_string_for_xml(target, True))
        p = c.position()
        c.insertText('</a>')
        c.setPosition(p)  # ensure cursor is positioned inside the newly created tag
        if text:
            c.insertText(text)
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

    def cursor_position_with_sourceline(self, cursor):
        ''' Return the tag containing the current cursor as a source line
        number and a list of tags defined on that line upto and including the
        containing tag. '''
        block = cursor.block()
        offset = cursor.position() - block.position()
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
                block, offset = block.previous(), sys.maxint
        if start_block is None:
            return None, None
        sourceline = start_block.blockNumber() + 1  # blockNumber() is zero based
        ud = start_block.userData()
        if ud is None:
            return None, None
        all_tags = [t.name for t in ud.tags if (t.is_start and not t.closing and t.offset <= start_offset)]
        return sourceline, all_tags

    def goto_sourceline(self, editor, sourceline, tags, attribute=None):
        ''' Move the cursor to the tag identified by sourceline and tags (a
        list of tags names on the specified line). If attribute is specified
        the cursor will be placed at the start of the attribute value. '''
        block = editor.document().findBlockByNumber(sourceline - 1)  # blockNumber() is zero based
        found_tag = False
        if not block.isValid():
            return found_tag
        c = editor.textCursor()
        ud = block.userData()
        all_tags = [] if ud is None else [t for t in ud.tags if (t.is_start and not t.closing)]
        tag_names = [t.name for t in all_tags]
        if tag_names[:len(tags)] == tags:
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

