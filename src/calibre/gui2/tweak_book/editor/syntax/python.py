#!/usr/bin/env python
# License: GPLv3 Copyright: 2014, Kovid Goyal <kovid at kovidgoyal.net>

from pygments.lexers.python import PythonLexer

from calibre.gui2.tweak_book.editor.syntax.pygments_highlighter import create_highlighter

Highlighter = create_highlighter('PythonHighlighter', PythonLexer)

if __name__ == '__main__':
    import os

    from calibre.gui2.tweak_book.editor.widget import launch_editor

    launch_editor(os.path.abspath(__file__), syntax='python')
