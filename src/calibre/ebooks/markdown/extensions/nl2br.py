"""
NL2BR Extension
===============

A Python-Markdown extension to treat newlines as hard breaks; like
GitHub-flavored Markdown does.

See <https://pythonhosted.org/Markdown/extensions/nl2br.html>
for documentation.

Oringinal code Copyright 2011 [Brian Neal](http://deathofagremmie.com/)

All changes Copyright 2011-2014 The Python Markdown Project

License: [BSD](http://www.opensource.org/licenses/bsd-license.php)

"""

from __future__ import absolute_import
from __future__ import unicode_literals
from . import Extension
from ..inlinepatterns import SubstituteTagPattern

BR_RE = r'\n'


class Nl2BrExtension(Extension):

    def extendMarkdown(self, md, md_globals):
        br_tag = SubstituteTagPattern(BR_RE, 'br')
        md.inlinePatterns.add('nl', br_tag, '_end')


def makeExtension(*args, **kwargs):
    return Nl2BrExtension(*args, **kwargs)
