"""
Sane List Extension for Python-Markdown
=======================================

Modify the behavior of Lists in Python-Markdown to act in a sane manor.

See <https://pythonhosted.org/Markdown/extensions/sane_lists.html>
for documentation.

Original code Copyright 2011 [Waylan Limberg](http://achinghead.com)

All changes Copyright 2011-2014 The Python Markdown Project

License: [BSD](http://www.opensource.org/licenses/bsd-license.php)

"""

from __future__ import absolute_import
from __future__ import unicode_literals
from . import Extension
from ..blockprocessors import OListProcessor, UListProcessor
import re


class SaneOListProcessor(OListProcessor):

    SIBLING_TAGS = ['ol']

    def __init__(self, parser):
        super(SaneOListProcessor, self).__init__(parser)
        self.CHILD_RE = re.compile(r'^[ ]{0,%d}((\d+\.))[ ]+(.*)' %
                                   (self.tab_length - 1))


class SaneUListProcessor(UListProcessor):

    SIBLING_TAGS = ['ul']

    def __init__(self, parser):
        super(SaneUListProcessor, self).__init__(parser)
        self.CHILD_RE = re.compile(r'^[ ]{0,%d}(([*+-]))[ ]+(.*)' %
                                   (self.tab_length - 1))


class SaneListExtension(Extension):
    """ Add sane lists to Markdown. """

    def extendMarkdown(self, md, md_globals):
        """ Override existing Processors. """
        md.parser.blockprocessors['olist'] = SaneOListProcessor(md.parser)
        md.parser.blockprocessors['ulist'] = SaneUListProcessor(md.parser)


def makeExtension(*args, **kwargs):
    return SaneListExtension(*args, **kwargs)
