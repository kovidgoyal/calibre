# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import re
import sys


"""
Python 3 Stuff
=============================================================================
"""
PY3 = sys.version_info[0] == 3

if PY3:  # pragma: no cover
    string_type = str
    text_type = str
    int2str = chr
else:  # pragma: no cover
    string_type = basestring   # noqa
    text_type = unicode        # noqa
    int2str = unichr           # noqa


"""
Constants you might want to modify
-----------------------------------------------------------------------------
"""


BLOCK_LEVEL_ELEMENTS = re.compile(
    "^(p|div|h[1-6]|blockquote|pre|table|dl|ol|ul"
    "|script|noscript|form|fieldset|iframe|math"
    "|hr|hr/|style|li|dt|dd|thead|tbody"
    "|tr|th|td|section|footer|header|group|figure"
    "|figcaption|aside|article|canvas|output"
    "|progress|video|nav)$",
    re.IGNORECASE
)
# Placeholders
STX = '\u0002'  # Use STX ("Start of text") for start-of-placeholder
ETX = '\u0003'  # Use ETX ("End of text") for end-of-placeholder
INLINE_PLACEHOLDER_PREFIX = STX+"klzzwxh:"
INLINE_PLACEHOLDER = INLINE_PLACEHOLDER_PREFIX + "%s" + ETX
INLINE_PLACEHOLDER_RE = re.compile(INLINE_PLACEHOLDER % r'([0-9]+)')
AMP_SUBSTITUTE = STX+"amp"+ETX
HTML_PLACEHOLDER = STX + "wzxhzdk:%s" + ETX
HTML_PLACEHOLDER_RE = re.compile(HTML_PLACEHOLDER % r'([0-9]+)')
TAG_PLACEHOLDER = STX + "hzzhzkh:%s" + ETX


"""
Constants you probably do not need to change
-----------------------------------------------------------------------------
"""

RTL_BIDI_RANGES = (
    ('\u0590', '\u07FF'),
    # Hebrew (0590-05FF), Arabic (0600-06FF),
    # Syriac (0700-074F), Arabic supplement (0750-077F),
    # Thaana (0780-07BF), Nko (07C0-07FF).
    ('\u2D30', '\u2D7F')  # Tifinagh
)

# Extensions should use "markdown.util.etree" instead of "etree" (or do `from
# markdown.util import etree`).  Do not import it by yourself.

try:  # pragma: no cover
    # Is the C implementation of ElementTree available?
    import xml.etree.cElementTree as etree
    from xml.etree.ElementTree import Comment
    # Serializers (including ours) test with non-c Comment
    etree.test_comment = Comment
    if etree.VERSION < "1.0.5":
        raise RuntimeError("cElementTree version 1.0.5 or higher is required.")
except (ImportError, RuntimeError):  # pragma: no cover
    # Use the Python implementation of ElementTree?
    import xml.etree.ElementTree as etree
    if etree.VERSION < "1.1":
        raise RuntimeError("ElementTree version 1.1 or higher is required")


"""
AUXILIARY GLOBAL FUNCTIONS
=============================================================================
"""


def isBlockLevel(tag):
    """Check if the tag is a block level HTML tag."""
    if isinstance(tag, string_type):
        return BLOCK_LEVEL_ELEMENTS.match(tag)
    # Some ElementTree tags are not strings, so return False.
    return False


def parseBoolValue(value, fail_on_errors=True, preserve_none=False):
    """Parses a string representing bool value. If parsing was successful,
       returns True or False. If preserve_none=True, returns True, False,
       or None. If parsing was not successful, raises  ValueError, or, if
       fail_on_errors=False, returns None."""
    if not isinstance(value, string_type):
        if preserve_none and value is None:
            return value
        return bool(value)
    elif preserve_none and value.lower() == 'none':
        return None
    elif value.lower() in ('true', 'yes', 'y', 'on', '1'):
        return True
    elif value.lower() in ('false', 'no', 'n', 'off', '0', 'none'):
        return False
    elif fail_on_errors:
        raise ValueError('Cannot parse bool value: %r' % value)


"""
MISC AUXILIARY CLASSES
=============================================================================
"""


class AtomicString(text_type):
    """A string which should not be further processed."""
    pass


class Processor(object):
    def __init__(self, markdown_instance=None):
        if markdown_instance:
            self.markdown = markdown_instance


class HtmlStash(object):
    """
    This class is used for stashing HTML objects that we extract
    in the beginning and replace with place-holders.
    """

    def __init__(self):
        """ Create a HtmlStash. """
        self.html_counter = 0  # for counting inline html segments
        self.rawHtmlBlocks = []
        self.tag_counter = 0
        self.tag_data = []  # list of dictionaries in the order tags appear

    def store(self, html, safe=False):
        """
        Saves an HTML segment for later reinsertion.  Returns a
        placeholder string that needs to be inserted into the
        document.

        Keyword arguments:

        * html: an html segment
        * safe: label an html segment as safe for safemode

        Returns : a placeholder string

        """
        self.rawHtmlBlocks.append((html, safe))
        placeholder = self.get_placeholder(self.html_counter)
        self.html_counter += 1
        return placeholder

    def reset(self):
        self.html_counter = 0
        self.rawHtmlBlocks = []

    def get_placeholder(self, key):
        return HTML_PLACEHOLDER % key

    def store_tag(self, tag, attrs, left_index, right_index):
        """Store tag data and return a placeholder."""
        self.tag_data.append({'tag': tag, 'attrs': attrs,
                              'left_index': left_index,
                              'right_index': right_index})
        placeholder = TAG_PLACEHOLDER % str(self.tag_counter)
        self.tag_counter += 1  # equal to the tag's index in self.tag_data
        return placeholder
