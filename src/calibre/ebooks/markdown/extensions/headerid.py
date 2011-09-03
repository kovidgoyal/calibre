#!/usr/bin/python

"""
HeaderID Extension for Python-Markdown
======================================

Adds ability to set HTML IDs for headers.

Basic usage:

    >>> import markdown
    >>> text = "# Some Header # {#some_id}"
    >>> md = markdown.markdown(text, ['headerid'])
    >>> md
    u'<h1 id="some_id">Some Header</h1>'

All header IDs are unique:

    >>> text = '''
    ... #Header
    ... #Another Header {#header}
    ... #Third Header {#header}'''
    >>> md = markdown.markdown(text, ['headerid'])
    >>> md
    u'<h1 id="header">Header</h1>\\n<h1 id="header_1">Another Header</h1>\\n<h1 id="header_2">Third Header</h1>'

To fit within a html template's hierarchy, set the header base level:

    >>> text = '''
    ... #Some Header
    ... ## Next Level'''
    >>> md = markdown.markdown(text, ['headerid(level=3)'])
    >>> md
    u'<h3 id="some_header">Some Header</h3>\\n<h4 id="next_level">Next Level</h4>'

Turn off auto generated IDs:

    >>> text = '''
    ... # Some Header
    ... # Header with ID # { #foo }'''
    >>> md = markdown.markdown(text, ['headerid(forceid=False)'])
    >>> md
    u'<h1>Some Header</h1>\\n<h1 id="foo">Header with ID</h1>'

Use with MetaData extension:

    >>> text = '''header_level: 2
    ... header_forceid: Off
    ...
    ... # A Header'''
    >>> md = markdown.markdown(text, ['headerid', 'meta'])
    >>> md
    u'<h2>A Header</h2>'

Copyright 2007-2008 [Waylan Limberg](http://achinghead.com/).

Project website: <http://www.freewisdom.org/project/python-markdown/HeaderId>
Contact: markdown@freewisdom.org

License: BSD (see ../docs/LICENSE for details)

Dependencies:
* [Python 2.3+](http://python.org)
* [Markdown 2.0+](http://www.freewisdom.org/projects/python-markdown/)

"""

import calibre.ebooks.markdown.markdown as markdown
import re
from string import ascii_lowercase, digits, punctuation

ID_CHARS = ascii_lowercase + digits + '-_'
IDCOUNT_RE = re.compile(r'^(.*)_([0-9]+)$')


class HeaderIdProcessor(markdown.blockprocessors.BlockProcessor):
    """ Replacement BlockProcessor for Header IDs. """

    # Detect a header at start of any line in block
    RE = re.compile(r"""(^|\n)
                        (?P<level>\#{1,6})  # group('level') = string of hashes
                        (?P<header>.*?)     # group('header') = Header text
                        \#*                 # optional closing hashes
                        (?:[ \t]*\{[ \t]*\#(?P<id>[-_:a-zA-Z0-9]+)[ \t]*\})?
                        (\n|$)              #  ^^ group('id') = id attribute
                     """,
                     re.VERBOSE)

    IDs = []

    def test(self, parent, block):
        return bool(self.RE.search(block))

    def run(self, parent, blocks):
        block = blocks.pop(0)
        m = self.RE.search(block)
        if m:
            before = block[:m.start()] # All lines before header
            after = block[m.end():]    # All lines after header
            if before:
                # As the header was not the first line of the block and the
                # lines before the header must be parsed first,
                # recursively parse this lines as a block.
                self.parser.parseBlocks(parent, [before])
            # Create header using named groups from RE
            start_level, force_id = self._get_meta()
            level = len(m.group('level')) + start_level
            if level > 6:
                level = 6
            h = markdown.etree.SubElement(parent, 'h%d' % level)
            h.text = m.group('header').strip()
            if m.group('id'):
                h.set('id', self._unique_id(m.group('id')))
            elif force_id:
                h.set('id', self._create_id(m.group('header').strip()))
            if after:
                # Insert remaining lines as first block for future parsing.
                blocks.insert(0, after)
        else:
            # This should never happen, but just in case...
            print ("We've got a problem header!")

    def _get_meta(self):
        """ Return meta data suported by this ext as a tuple """
        level = int(self.config['level'][0]) - 1
        force = self._str2bool(self.config['forceid'][0])
        if hasattr(self.md, 'Meta'):
            if self.md.Meta.has_key('header_level'):
                level = int(self.md.Meta['header_level'][0]) - 1
            if self.md.Meta.has_key('header_forceid'):
                force = self._str2bool(self.md.Meta['header_forceid'][0])
        return level, force

    def _str2bool(self, s, default=False):
        """ Convert a string to a booleen value. """
        s = str(s)
        if s.lower() in ['0', 'f', 'false', 'off', 'no', 'n']:
            return False
        elif s.lower() in ['1', 't', 'true', 'on', 'yes', 'y']:
            return True
        return default

    def _unique_id(self, id):
        """ Ensure ID is unique. Append '_1', '_2'... if not """
        while id in self.IDs:
            m = IDCOUNT_RE.match(id)
            if m:
                id = '%s_%d'% (m.group(1), int(m.group(2))+1)
            else:
                id = '%s_%d'% (id, 1)
        self.IDs.append(id)
        return id

    def _create_id(self, header):
        """ Return ID from Header text. """
        h = ''
        for c in header.lower().replace(' ', '_'):
            if c in ID_CHARS:
                h += c
            elif c not in punctuation:
                h += '+'
        return self._unique_id(h)


class HeaderIdExtension (markdown.Extension):
    def __init__(self, configs):
        # set defaults
        self.config = {
                'level' : ['1', 'Base level for headers.'],
                'forceid' : ['True', 'Force all headers to have an id.']
            }

        for key, value in configs:
            self.setConfig(key, value)

    def extendMarkdown(self, md, md_globals):
        md.registerExtension(self)
        self.processor = HeaderIdProcessor(md.parser)
        self.processor.md = md
        self.processor.config = self.config
        # Replace existing hasheader in place.
        md.parser.blockprocessors['hashheader'] = self.processor

    def reset(self):
        self.processor.IDs = []


def makeExtension(configs=None):
    return HeaderIdExtension(configs=configs)

if __name__ == "__main__":
    import doctest
    doctest.testmod()

