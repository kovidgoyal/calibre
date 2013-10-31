'''
Smart_Strong Extension for Python-Markdown
==========================================

This extention adds smarter handling of double underscores within words.

Simple Usage:

    >>> import markdown
    >>> print markdown.markdown('Text with double__underscore__words.',
    ...                   extensions=['smart_strong'])
    <p>Text with double__underscore__words.</p>
    >>> print markdown.markdown('__Strong__ still works.',
    ...                   extensions=['smart_strong'])
    <p><strong>Strong</strong> still works.</p>
    >>> print markdown.markdown('__this__works__too__.',
    ...                   extensions=['smart_strong'])
    <p><strong>this__works__too</strong>.</p>

Copyright 2011
[Waylan Limberg](http://achinghead.com)

'''

from __future__ import absolute_import
from __future__ import unicode_literals
from . import Extension
from ..inlinepatterns import SimpleTagPattern

SMART_STRONG_RE = r'(?<!\w)(_{2})(?!_)(.+?)(?<!_)\2(?!\w)'
STRONG_RE = r'(\*{2})(.+?)\2'

class SmartEmphasisExtension(Extension):
    """ Add smart_emphasis extension to Markdown class."""

    def extendMarkdown(self, md, md_globals):
        """ Modify inline patterns. """
        md.inlinePatterns['strong'] = SimpleTagPattern(STRONG_RE, 'strong')
        md.inlinePatterns.add('strong2', SimpleTagPattern(SMART_STRONG_RE, 'strong'), '>emphasis2')

def makeExtension(configs={}):
    return SmartEmphasisExtension(configs=dict(configs))
