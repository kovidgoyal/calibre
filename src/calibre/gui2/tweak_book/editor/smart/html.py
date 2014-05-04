#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import sys, re
from operator import itemgetter
from . import NullSmarts

from PyQt4.Qt import QTextEdit

from calibre import prepare_string_for_xml
from calibre.gui2 import error_dialog
from calibre.gui2.tweak_book.editor.syntax.html import ATTR_NAME, ATTR_END

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

class HTMLSmarts(NullSmarts):

    def get_extra_selections(self, editor):
        ans = []

        def add_tag(tag):
            a = QTextEdit.ExtraSelection()
            a.cursor, a.format = editor.textCursor(), editor.match_paren_format
            a.cursor.setPosition(tag.start_block.position() + tag.start_offset)
            a.cursor.setPosition(tag.end_block.position() + tag.end_offset + 1, a.cursor.KeepAnchor)
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
        c = editor.textCursor()
        block, offset = c.block(), c.positionInBlock()
        tag = None

        while True:
            tag = find_closest_containing_tag(block, offset)
            if tag is None:
                break
            block, offset = tag.start_block, tag.start_offset
            if tag.name in {
                    'address', 'article', 'aside', 'blockquote', 'center',
                    'dir', 'fieldset', 'isindex', 'menu', 'noframes', 'hgroup',
                    'noscript', 'pre', 'section', 'h1', 'h2', 'h3', 'h4', 'h5',
                    'h6', 'header', 'p', 'div', 'dd', 'dl', 'ul', 'ol', 'li', 'body',
                    'td', 'th'}:
                break
            tag = None

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
        text = self.get_smart_selection(editor, update=True)
        c = editor.textCursor()
        pos = min(c.position(), c.anchor())
        c.insertText('<{0}>{1}</{0}>'.format(name, text))
        c.setPosition(pos + 1 + len(name))
        editor.setTextCursor(c)

    def verify_for_spellcheck(self, cursor, highlighter):
        # Return True iff the cursor is in a location where spelling is
        # checked (inside a tag or inside a checked attribute)
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

