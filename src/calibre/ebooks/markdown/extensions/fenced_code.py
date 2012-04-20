#!/usr/bin/env python

"""
Fenced Code Extension for Python Markdown
=========================================

This extension adds Fenced Code Blocks to Python-Markdown.

    >>> import markdown
    >>> text = '''
    ... A paragraph before a fenced code block:
    ... 
    ... ~~~
    ... Fenced code block
    ... ~~~
    ... '''
    >>> html = markdown.markdown(text, extensions=['fenced_code'])
    >>> html
    u'<p>A paragraph before a fenced code block:</p>\\n<pre><code>Fenced code block\\n</code></pre>'

Works with safe_mode also (we check this because we are using the HtmlStash):

    >>> markdown.markdown(text, extensions=['fenced_code'], safe_mode='replace')
    u'<p>A paragraph before a fenced code block:</p>\\n<pre><code>Fenced code block\\n</code></pre>'
    
Include tilde's in a code block and wrap with blank lines:

    >>> text = '''
    ... ~~~~~~~~
    ... 
    ... ~~~~
    ... 
    ... ~~~~~~~~'''
    >>> markdown.markdown(text, extensions=['fenced_code'])
    u'<pre><code>\\n~~~~\\n\\n</code></pre>'

Multiple blocks and language tags:

    >>> text = '''
    ... ~~~~{.python}
    ... block one
    ... ~~~~
    ... 
    ... ~~~~.html
    ... <p>block two</p>
    ... ~~~~'''
    >>> markdown.markdown(text, extensions=['fenced_code'])
    u'<pre><code class="python">block one\\n</code></pre>\\n\\n<pre><code class="html">&lt;p&gt;block two&lt;/p&gt;\\n</code></pre>'

Copyright 2007-2008 [Waylan Limberg](http://achinghead.com/).

Project website: <http://www.freewisdom.org/project/python-markdown/Fenced__Code__Blocks>
Contact: markdown@freewisdom.org

License: BSD (see ../docs/LICENSE for details) 

Dependencies:
* [Python 2.3+](http://python.org)
* [Markdown 2.0+](http://www.freewisdom.org/projects/python-markdown/)

"""

import re
import calibre.ebooks.markdown.markdown as markdown

# Global vars
FENCED_BLOCK_RE = re.compile( \
    r'(?P<fence>^~{3,})[ ]*(\{?\.(?P<lang>[a-zA-Z0-9_-]*)\}?)?[ ]*\n(?P<code>.*?)(?P=fence)[ ]*$', 
    re.MULTILINE|re.DOTALL
    )
CODE_WRAP = '<pre><code%s>%s</code></pre>'
LANG_TAG = ' class="%s"'


class FencedCodeExtension(markdown.Extension):

    def extendMarkdown(self, md, md_globals):
        """ Add FencedBlockPreprocessor to the Markdown instance. """

        md.preprocessors.add('fenced_code_block', 
                                 FencedBlockPreprocessor(md), 
                                 "_begin")


class FencedBlockPreprocessor(markdown.preprocessors.Preprocessor):
    
    def run(self, lines):
        """ Match and store Fenced Code Blocks in the HtmlStash. """
        text = "\n".join(lines)
        while 1:
            m = FENCED_BLOCK_RE.search(text)
            if m:
                lang = ''
                if m.group('lang'):
                    lang = LANG_TAG % m.group('lang')
                code = CODE_WRAP % (lang, self._escape(m.group('code')))
                placeholder = self.markdown.htmlStash.store(code, safe=True)
                text = '%s\n%s\n%s'% (text[:m.start()], placeholder, text[m.end():])
            else:
                break
        return text.split("\n")

    def _escape(self, txt):
        """ basic html escaping """
        txt = txt.replace('&', '&amp;')
        txt = txt.replace('<', '&lt;')
        txt = txt.replace('>', '&gt;')
        txt = txt.replace('"', '&quot;')
        return txt


def makeExtension(configs=None):
    return FencedCodeExtension()


if __name__ == "__main__":
    import doctest
    doctest.testmod()
