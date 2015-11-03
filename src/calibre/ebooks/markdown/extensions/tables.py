"""
Tables Extension for Python-Markdown
====================================

Added parsing of tables to Python-Markdown.

See <https://pythonhosted.org/Markdown/extensions/tables.html>
for documentation.

Original code Copyright 2009 [Waylan Limberg](http://achinghead.com)

All changes Copyright 2008-2014 The Python Markdown Project

License: [BSD](http://www.opensource.org/licenses/bsd-license.php)

"""

from __future__ import absolute_import
from __future__ import unicode_literals
from . import Extension
from ..blockprocessors import BlockProcessor
from ..inlinepatterns import BacktickPattern, BACKTICK_RE
from ..util import etree


class TableProcessor(BlockProcessor):
    """ Process Tables. """

    def test(self, parent, block):
        rows = block.split('\n')
        return (len(rows) > 1 and '|' in rows[0] and
                '|' in rows[1] and '-' in rows[1] and
                rows[1].strip()[0] in ['|', ':', '-'])

    def run(self, parent, blocks):
        """ Parse a table block and build table. """
        block = blocks.pop(0).split('\n')
        header = block[0].strip()
        seperator = block[1].strip()
        rows = [] if len(block) < 3 else block[2:]
        # Get format type (bordered by pipes or not)
        border = False
        if header.startswith('|'):
            border = True
        # Get alignment of columns
        align = []
        for c in self._split_row(seperator, border):
            if c.startswith(':') and c.endswith(':'):
                align.append('center')
            elif c.startswith(':'):
                align.append('left')
            elif c.endswith(':'):
                align.append('right')
            else:
                align.append(None)
        # Build table
        table = etree.SubElement(parent, 'table')
        thead = etree.SubElement(table, 'thead')
        self._build_row(header, thead, align, border)
        tbody = etree.SubElement(table, 'tbody')
        for row in rows:
            self._build_row(row.strip(), tbody, align, border)

    def _build_row(self, row, parent, align, border):
        """ Given a row of text, build table cells. """
        tr = etree.SubElement(parent, 'tr')
        tag = 'td'
        if parent.tag == 'thead':
            tag = 'th'
        cells = self._split_row(row, border)
        # We use align here rather than cells to ensure every row
        # contains the same number of columns.
        for i, a in enumerate(align):
            c = etree.SubElement(tr, tag)
            try:
                if isinstance(cells[i], str) or isinstance(cells[i], unicode):
                    c.text = cells[i].strip()
                else:
                    # we've already inserted a code element
                    c.append(cells[i])
            except IndexError:  # pragma: no cover
                c.text = ""
            if a:
                c.set('align', a)

    def _split_row(self, row, border):
        """ split a row of text into list of cells. """
        if border:
            if row.startswith('|'):
                row = row[1:]
            if row.endswith('|'):
                row = row[:-1]
        return self._split(row, '|')

    def _split(self, row, marker):
        """ split a row of text with some code into a list of cells. """
        if self._row_has_unpaired_backticks(row):
            # fallback on old behaviour
            return row.split(marker)
        # modify the backtick pattern to only match at the beginning of the search string
        backtick_pattern = BacktickPattern('^' + BACKTICK_RE)
        elements = []
        current = ''
        i = 0
        while i < len(row):
            letter = row[i]
            if letter == marker:
                if current != '' or len(elements) == 0:
                    # Don't append empty string unless it is the first element
                    # The border is already removed when we get the row, then the line is strip()'d
                    # If the first element is a marker, then we have an empty first cell
                    elements.append(current)
                current = ''
            else:
                match = backtick_pattern.getCompiledRegExp().match(row[i:])
                if not match:
                    current += letter
                else:
                    groups = match.groups()
                    delim = groups[1]  # the code block delimeter (ie 1 or more backticks)
                    row_contents = groups[2]  # the text contained inside the code block
                    i += match.start(4)  # jump pointer to the beginning of the rest of the text (group #4)
                    element = delim + row_contents + delim  # reinstert backticks
                    current += element
            i += 1
        elements.append(current)
        return elements

    def _row_has_unpaired_backticks(self, row):
        count_total_backtick = row.count('`')
        count_escaped_backtick = row.count('\`')
        count_backtick = count_total_backtick - count_escaped_backtick
        # odd number of backticks,
        # we won't be able to build correct code blocks
        return count_backtick & 1


class TableExtension(Extension):
    """ Add tables to Markdown. """

    def extendMarkdown(self, md, md_globals):
        """ Add an instance of TableProcessor to BlockParser. """
        md.parser.blockprocessors.add('table',
                                      TableProcessor(md.parser),
                                      '<hashheader')


def makeExtension(*args, **kwargs):
    return TableExtension(*args, **kwargs)
