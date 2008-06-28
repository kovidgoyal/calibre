# -*- coding: utf-8 -*-
#
# Copyright (C) 2006-2008 Edgewall Software
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://genshi.edgewall.org/wiki/License.
#
# This software consists of voluntary contributions made by many
# individuals. For the exact contribution history, see the revision
# history and logs, available at http://genshi.edgewall.org/log/.

"""Plain text templating engine.

This module implements two template language syntaxes, at least for a certain
transitional period. `OldTextTemplate` (aliased to just `TextTemplate`) defines
a syntax that was inspired by Cheetah/Velocity. `NewTextTemplate` on the other
hand is inspired by the syntax of the Django template language, which has more
explicit delimiting of directives, and is more flexible with regards to
white space and line breaks.

In a future release, `OldTextTemplate` will be phased out in favor of
`NewTextTemplate`, as the names imply. Therefore the new syntax is strongly
recommended for new projects, and existing projects may want to migrate to the
new syntax to remain compatible with future Genshi releases.
"""

import re

from calibre.utils.genshi.core import TEXT
from calibre.utils.genshi.template.base import BadDirectiveError, Template, \
                                 TemplateSyntaxError, EXEC, INCLUDE, SUB
from calibre.utils.genshi.template.eval import Suite
from calibre.utils.genshi.template.directives import *
from calibre.utils.genshi.template.directives import Directive
from calibre.utils.genshi.template.interpolation import interpolate

__all__ = ['NewTextTemplate', 'OldTextTemplate', 'TextTemplate']
__docformat__ = 'restructuredtext en'


class NewTextTemplate(Template):
    r"""Implementation of a simple text-based template engine. This class will
    replace `OldTextTemplate` in a future release.
    
    It uses a more explicit delimiting style for directives: instead of the old
    style which required putting directives on separate lines that were prefixed
    with a ``#`` sign, directives and commenbtsr are enclosed in delimiter pairs
    (by default ``{% ... %}`` and ``{# ... #}``, respectively).
    
    Variable substitution uses the same interpolation syntax as for markup
    languages: simple references are prefixed with a dollar sign, more complex
    expression enclosed in curly braces.
    
    >>> tmpl = NewTextTemplate('''Dear $name,
    ... 
    ... {# This is a comment #}
    ... We have the following items for you:
    ... {% for item in items %}
    ...  * ${'Item %d' % item}
    ... {% end %}
    ... ''')
    >>> print tmpl.generate(name='Joe', items=[1, 2, 3]).render()
    Dear Joe,
    <BLANKLINE>
    <BLANKLINE>
    We have the following items for you:
    <BLANKLINE>
     * Item 1
    <BLANKLINE>
     * Item 2
    <BLANKLINE>
     * Item 3
    <BLANKLINE>
    <BLANKLINE>
    
    By default, no spaces or line breaks are removed. If a line break should
    not be included in the output, prefix it with a backslash:
    
    >>> tmpl = NewTextTemplate('''Dear $name,
    ... 
    ... {# This is a comment #}\
    ... We have the following items for you:
    ... {% for item in items %}\
    ...  * $item
    ... {% end %}\
    ... ''')
    >>> print tmpl.generate(name='Joe', items=[1, 2, 3]).render()
    Dear Joe,
    <BLANKLINE>
    We have the following items for you:
     * 1
     * 2
     * 3
    <BLANKLINE>
    
    Backslashes are also used to escape the start delimiter of directives and
    comments:

    >>> tmpl = NewTextTemplate('''Dear $name,
    ... 
    ... \{# This is a comment #}
    ... We have the following items for you:
    ... {% for item in items %}\
    ...  * $item
    ... {% end %}\
    ... ''')
    >>> print tmpl.generate(name='Joe', items=[1, 2, 3]).render()
    Dear Joe,
    <BLANKLINE>
    {# This is a comment #}
    We have the following items for you:
     * 1
     * 2
     * 3
    <BLANKLINE>
    
    :since: version 0.5
    """
    directives = [('def', DefDirective),
                  ('when', WhenDirective),
                  ('otherwise', OtherwiseDirective),
                  ('for', ForDirective),
                  ('if', IfDirective),
                  ('choose', ChooseDirective),
                  ('with', WithDirective)]
    serializer = 'text'

    _DIRECTIVE_RE = r'((?<!\\)%s\s*(\w+)\s*(.*?)\s*%s|(?<!\\)%s.*?%s)'
    _ESCAPE_RE = r'\\\n|\\(\\)|\\(%s)|\\(%s)'

    def __init__(self, source, filepath=None, filename=None, loader=None,
                 encoding=None, lookup='strict', allow_exec=False,
                 delims=('{%', '%}', '{#', '#}')):
        self.delimiters = delims
        Template.__init__(self, source, filepath=filepath, filename=filename,
                          loader=loader, encoding=encoding, lookup=lookup)

    def _get_delims(self):
        return self._delims
    def _set_delims(self, delims):
        if len(delims) != 4:
            raise ValueError('delimiers tuple must have exactly four elements')
        self._delims = delims
        self._directive_re = re.compile(self._DIRECTIVE_RE % tuple(
            map(re.escape, delims)
        ), re.DOTALL)
        self._escape_re = re.compile(self._ESCAPE_RE % tuple(
            map(re.escape, delims[::2])
        ))
    delimiters = property(_get_delims, _set_delims, """\
    The delimiters for directives and comments. This should be a four item tuple
    of the form ``(directive_start, directive_end, comment_start,
    comment_end)``, where each item is a string.
    """)

    def _parse(self, source, encoding):
        """Parse the template from text input."""
        stream = [] # list of events of the "compiled" template
        dirmap = {} # temporary mapping of directives to elements
        depth = 0

        source = source.read()
        if isinstance(source, str):
            source = source.decode(encoding or 'utf-8', 'replace')
        offset = 0
        lineno = 1

        _escape_sub = self._escape_re.sub
        def _escape_repl(mo):
            groups = filter(None, mo.groups()) 
            if not groups:
                return ''
            return groups[0]

        for idx, mo in enumerate(self._directive_re.finditer(source)):
            start, end = mo.span(1)
            if start > offset:
                text = _escape_sub(_escape_repl, source[offset:start])
                for kind, data, pos in interpolate(text, self.filepath, lineno,
                                                   lookup=self.lookup):
                    stream.append((kind, data, pos))
                lineno += len(text.splitlines())

            lineno += len(source[start:end].splitlines())
            command, value = mo.group(2, 3)

            if command == 'include':
                pos = (self.filename, lineno, 0)
                value = list(interpolate(value, self.filepath, lineno, 0,
                                         lookup=self.lookup))
                if len(value) == 1 and value[0][0] is TEXT:
                    value = value[0][1]
                stream.append((INCLUDE, (value, None, []), pos))

            elif command == 'python':
                if not self.allow_exec:
                    raise TemplateSyntaxError('Python code blocks not allowed',
                                              self.filepath, lineno)
                try:
                    suite = Suite(value, self.filepath, lineno,
                                  lookup=self.lookup)
                except SyntaxError, err:
                    raise TemplateSyntaxError(err, self.filepath,
                                              lineno + (err.lineno or 1) - 1)
                pos = (self.filename, lineno, 0)
                stream.append((EXEC, suite, pos))

            elif command == 'end':
                depth -= 1
                if depth in dirmap:
                    directive, start_offset = dirmap.pop(depth)
                    substream = stream[start_offset:]
                    stream[start_offset:] = [(SUB, ([directive], substream),
                                              (self.filepath, lineno, 0))]

            elif command:
                cls = self._dir_by_name.get(command)
                if cls is None:
                    raise BadDirectiveError(command)
                directive = cls, value, None, (self.filepath, lineno, 0)
                dirmap[depth] = (directive, len(stream))
                depth += 1

            offset = end

        if offset < len(source):
            text = _escape_sub(_escape_repl, source[offset:])
            for kind, data, pos in interpolate(text, self.filepath, lineno,
                                               lookup=self.lookup):
                stream.append((kind, data, pos))

        return stream


class OldTextTemplate(Template):
    """Legacy implementation of the old syntax text-based templates. This class
    is provided in a transition phase for backwards compatibility. New code
    should use the `NewTextTemplate` class and the improved syntax it provides.
    
    >>> tmpl = OldTextTemplate('''Dear $name,
    ... 
    ... We have the following items for you:
    ... #for item in items
    ...  * $item
    ... #end
    ... 
    ... All the best,
    ... Foobar''')
    >>> print tmpl.generate(name='Joe', items=[1, 2, 3]).render()
    Dear Joe,
    <BLANKLINE>
    We have the following items for you:
     * 1
     * 2
     * 3
    <BLANKLINE>
    All the best,
    Foobar
    """
    directives = [('def', DefDirective),
                  ('when', WhenDirective),
                  ('otherwise', OtherwiseDirective),
                  ('for', ForDirective),
                  ('if', IfDirective),
                  ('choose', ChooseDirective),
                  ('with', WithDirective)]
    serializer = 'text'

    _DIRECTIVE_RE = re.compile(r'(?:^[ \t]*(?<!\\)#(end).*\n?)|'
                               r'(?:^[ \t]*(?<!\\)#((?:\w+|#).*)\n?)',
                               re.MULTILINE)

    def _parse(self, source, encoding):
        """Parse the template from text input."""
        stream = [] # list of events of the "compiled" template
        dirmap = {} # temporary mapping of directives to elements
        depth = 0

        source = source.read()
        if isinstance(source, str):
            source = source.decode(encoding or 'utf-8', 'replace')
        offset = 0
        lineno = 1

        for idx, mo in enumerate(self._DIRECTIVE_RE.finditer(source)):
            start, end = mo.span()
            if start > offset:
                text = source[offset:start]
                for kind, data, pos in interpolate(text, self.filepath, lineno,
                                                   lookup=self.lookup):
                    stream.append((kind, data, pos))
                lineno += len(text.splitlines())

            text = source[start:end].lstrip()[1:]
            lineno += len(text.splitlines())
            directive = text.split(None, 1)
            if len(directive) > 1:
                command, value = directive
            else:
                command, value = directive[0], None

            if command == 'end':
                depth -= 1
                if depth in dirmap:
                    directive, start_offset = dirmap.pop(depth)
                    substream = stream[start_offset:]
                    stream[start_offset:] = [(SUB, ([directive], substream),
                                              (self.filepath, lineno, 0))]
            elif command == 'include':
                pos = (self.filename, lineno, 0)
                stream.append((INCLUDE, (value.strip(), None, []), pos))
            elif command != '#':
                cls = self._dir_by_name.get(command)
                if cls is None:
                    raise BadDirectiveError(command)
                directive = cls, value, None, (self.filepath, lineno, 0)
                dirmap[depth] = (directive, len(stream))
                depth += 1

            offset = end

        if offset < len(source):
            text = source[offset:].replace('\\#', '#')
            for kind, data, pos in interpolate(text, self.filepath, lineno,
                                               lookup=self.lookup):
                stream.append((kind, data, pos))

        return stream


TextTemplate = OldTextTemplate
