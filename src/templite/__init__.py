#!/usr/bin/env python
#
#       Templite+
#       A light-weight, fully functional, general purpose templating engine
#
#       Copyright (c) 2009 joonis new media
#       Author: Thimo Kraemer <thimo.kraemer@joonis.de>
#
#       Based on Templite - Tomer Filiba
#       http://code.activestate.com/recipes/496702/
#
#       This program is free software; you can redistribute it and/or modify
#       it under the terms of the GNU General Public License as published by
#       the Free Software Foundation; either version 2 of the License, or
#       (at your option) any later version.
#
#       This program is distributed in the hope that it will be useful,
#       but WITHOUT ANY WARRANTY; without even the implied warranty of
#       MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#       GNU General Public License for more details.
#
#       You should have received a copy of the GNU General Public License
#       along with this program; if not, write to the Free Software
#       Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#       MA 02110-1301, USA.
#

import sys, re

from polyglot.builtins import unicode_type

class Templite:
    auto_emit = re.compile('(^[\'\"])|(^[a-zA-Z0-9_\[\]\'\"]+$)')

    def __init__(self, template, start='${', end='}$'):
        if len(start) != 2 or len(end) != 2:
            raise ValueError('each delimiter must be two characters long')
        delimiter = re.compile('%s(.*?)%s' % (re.escape(start), re.escape(end)), re.DOTALL)
        offset = 0
        tokens = []
        for i, part in enumerate(delimiter.split(template)):
            part = part.replace('\\'.join(list(start)), start)
            part = part.replace('\\'.join(list(end)), end)
            if i % 2 == 0:
                if not part: continue
                part = part.replace('\\', '\\\\').replace('"', '\\"')
                part = '\t' * offset + 'emit("""%s""")' % part
            else:
                part = part.rstrip()
                if not part: continue
                if part.lstrip().startswith(':'):
                    if not offset:
                        raise SyntaxError('no block statement to terminate: ${%s}$' % part)
                    offset -= 1
                    part = part.lstrip()[1:]
                    if not part.endswith(':'): continue
                elif self.auto_emit.match(part.lstrip()):
                    part = 'emit(%s)' % part.lstrip()
                lines = part.splitlines()
                margin = min(len(l) - len(l.lstrip()) for l in lines if l.strip())
                part = '\n'.join('\t' * offset + l[margin:] for l in lines)
                if part.endswith(':'):
                    offset += 1
            tokens.append(part)
        if offset:
            raise SyntaxError('%i block statement(s) not terminated' % offset)
        self.__code = compile('\n'.join(tokens), '<templite %r>' % template[:20], 'exec')

    def render(self, __namespace=None, **kw):
        """
        renders the template according to the given namespace.
        __namespace - a dictionary serving as a namespace for evaluation
        **kw - keyword arguments which are added to the namespace
        """
        namespace = {}
        if __namespace: namespace.update(__namespace)
        if kw: namespace.update(kw)
        namespace['emit'] = self.write

        __stdout = sys.stdout
        sys.stdout = self
        self.__output = []
        eval(self.__code, namespace)
        sys.stdout = __stdout
        return ''.join(self.__output)

    def write(self, *args):
        for a in args:
            self.__output.append(unicode_type(a))
