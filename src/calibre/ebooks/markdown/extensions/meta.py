#!usr/bin/python

"""
Meta Data Extension for Python-Markdown
=======================================

This extension adds Meta Data handling to markdown.

Basic Usage:

    >>> import markdown
    >>> text = '''Title: A Test Doc.
    ... Author: Waylan Limberg
    ...         John Doe
    ... Blank_Data:
    ...
    ... The body. This is paragraph one.
    ... '''
    >>> md = markdown.Markdown(['meta'])
    >>> md.convert(text)
    u'<p>The body. This is paragraph one.</p>'
    >>> md.Meta
    {u'blank_data': [u''], u'author': [u'Waylan Limberg', u'John Doe'], u'title': [u'A Test Doc.']}

Make sure text without Meta Data still works (markdown < 1.6b returns a <p>).

    >>> text = '    Some Code - not extra lines of meta data.'
    >>> md = markdown.Markdown(['meta'])
    >>> md.convert(text)
    u'<pre><code>Some Code - not extra lines of meta data.\\n</code></pre>'
    >>> md.Meta
    {}

Copyright 2007-2008 [Waylan Limberg](http://achinghead.com).

Project website: <http://www.freewisdom.org/project/python-markdown/Meta-Data>
Contact: markdown@freewisdom.org

License: BSD (see ../docs/LICENSE for details)

"""

import re
import calibre.ebooks.markdown.markdown as markdown

# Global Vars
META_RE = re.compile(r'^[ ]{0,3}(?P<key>[A-Za-z0-9_-]+):\s*(?P<value>.*)')
META_MORE_RE = re.compile(r'^[ ]{4,}(?P<value>.*)')

class MetaExtension (markdown.Extension):
    """ Meta-Data extension for Python-Markdown. """

    def extendMarkdown(self, md, md_globals):
        """ Add MetaPreprocessor to Markdown instance. """

        md.preprocessors.add("meta", MetaPreprocessor(md), "_begin")


class MetaPreprocessor(markdown.preprocessors.Preprocessor):
    """ Get Meta-Data. """

    def run(self, lines):
        """ Parse Meta-Data and store in Markdown.Meta. """
        meta = {}
        key = None
        while 1:
            line = lines.pop(0)
            if line.strip() == '':
                break # blank line - done
            m1 = META_RE.match(line)
            if m1:
                key = m1.group('key').lower().strip()
                meta[key] = [m1.group('value').strip()]
            else:
                m2 = META_MORE_RE.match(line)
                if m2 and key:
                    # Add another line to existing key
                    meta[key].append(m2.group('value').strip())
                else:
                    lines.insert(0, line)
                    break # no meta data - done
        self.markdown.Meta = meta
        return lines
        

def makeExtension(configs={}):
    return MetaExtension(configs=configs)

if __name__ == "__main__":
    import doctest
    doctest.testmod()
