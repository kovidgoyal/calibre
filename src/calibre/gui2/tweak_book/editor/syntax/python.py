#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

from pygments.lexers import PythonLexer

from calibre.gui2.tweak_book.editor.syntax.pygments_highlighter import create_highlighter

Highlighter = create_highlighter('PythonHighlighter', PythonLexer)

if __name__ == '__main__':
    import os
    from calibre.gui2.tweak_book.editor.widget import launch_editor
    launch_editor(os.path.abspath(__file__), syntax='python')
