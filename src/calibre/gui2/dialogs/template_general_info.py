#!/usr/bin/env python


__copyright__ = '2024, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'
__license__   = 'GPL v3'

'''
@author: Charles Haley
'''

from qt.core import QDialogButtonBox, QVBoxLayout

from calibre.constants import iswindows
from calibre.gui2.widgets2 import Dialog, HTMLDisplay
from calibre.utils.ffml_processor import FFMLProcessor


class GeneralInformationDialog(Dialog):

    def __init__(self, include_general_doc=False, include_ffml_doc=False, parent=None):
        self.include_general_doc = include_general_doc
        self.include_ffml_doc = include_ffml_doc
        super().__init__(title=_('Template function general information'), name='template_editor_gen_info_dialog',
                         default_buttons=QDialogButtonBox.StandardButton.Close, parent=parent)

    def setup_ui(self):
        l = QVBoxLayout(self)
        e = HTMLDisplay(self)
        l.addWidget(e)
        if iswindows:
            e.setDefaultStyleSheet('pre { font-family: "Segoe UI Mono", "Consolas", monospace; }')
        l.addWidget(self.bb)
        html = ''
        if self.include_general_doc:
                html += '<h2>General Information</h2>'
                html += FFMLProcessor().document_to_html(general_doc, 'Template General Information')
        if self.include_ffml_doc:
                html += '<h2>Format Function Markup Language Documentation</h2>'
                html += FFMLProcessor().document_to_html(ffml_doc, 'FFML Documentation')
        e.setHtml(html)


general_doc = r'''
[LIST]
[*]`Functions in Single Function Mode templates`
[LIST]
[*]When using functions in a Single function mode template,
for example ``{title:uppercase()}``, the first parameter ``value`` is omitted.
It is automatically replaced by the value of the specified field.

In all the other modes the value parameter must be supplied.
[*]Do not use subtemplates "(`{...}`)" as function arguments because they will often not work.
Instead, use Template Program Mode and General Program Mode.
[*]Do not use subtemplates "(`{...}`)" or functions (see below) in the prefix or the suffix
for the same reason as above; they will often not work.
[/LIST]
[*]`Editor for assisting with template function documentation`

An editor is available for helping write template function documentation. Given a document
in the Formatter Function Markup Language, it show the resulting HTML. The HTML is updated as you edit.

This editor is available in two ways:
[LIST]
[*]Using the command
[CODE]
calibre-debug -c "from calibre.gui2.dialogs.ff_doc_editor import main; main()"[/CODE]
all on one line.
[*]By defining a keyboard shortcut in calibre for the action `Open the template
documenation editor` in the `Miscellaneous` section. There is no default shortcut.
[/LIST]
[/LIST]
'''

ffml_doc = r'''
Format Function Markup Language (FFML) is a basic markup language used to
document formatter functions. It is based on a combination of RST used by sphinx
and BBCODE used by many bulletin board systems such as MobileRead. It provides a
way to specify:
[LIST]
[*][B]Inline program code text[/B]: surround this text with \`\` as in \`\`foo\`\`.
Tags inside the text are ignored. if the code text ends with a `\'` character, put
a space before the closing \`\` characters. Trailing blanks in the code text are removed.
[*][B]Italic text[/B]: surround this text with \`. Example: \`foo\` produces `foo`.
[*][B]Bold text[/B]: surround this text with \[B]text\[\B] tags. Example: \[B]foo\[/B] produces [B]foo[/B].
[*][B]Text intended to reference a calibre GUI action[/B]. This uses RST syntax.\
  Example: \:guilabel\:\`Preferences->Advanced->Template functions\`. For HTML the produced text is in a different font, as in: :guilabel:`Some text`
[*][B]Empty lines[/B], indicated by two newlines in a row. A visible empty line in the FFML
will become an empty line in the output.
[*][B]URLs.[/B] The syntax is similar to BBCODE: ``[URL href="http..."]Link text[/URL]``.\
  Example: ``[URL href="https://en.wikipedia.org/wiki/ISO_8601"]ISO[/URL]`` produces [URL href="https://en.wikipedia.org/wiki/ISO_8601"]ISO[/URL]
[*][B]Internal function reference links[/B]. These are links to formatter function
documentation. The syntax is the same as guilabel. Example: ``:ref:\`get_note\```.
The characters '()' are automatically added to the function name when
displayed. For HTML it generates the same as the inline program code text
operator (\`\`) with no link. Example: ``:ref:`add` `` produces ``add()``.
For RST it generates a ``:ref:`` reference that works only in an RST document
containing formatter function documentation. Example: ``:ref:\`get_note\```
generates \:ref\:\`get_note() <ff_get_note>\`
[*][B]Example program code text blocks.[/B] Surround the code block with ``[CODE]``
and ``[/CODE]`` tags. These tags must be first on a line. Example:
[CODE]
[CODE]program:
    get_note('authors', 'Isaac Asimov', 1)
[\/CODE]
[/CODE]
produces
[CODE]
program:
    get_note('authors', 'Isaac Asimov', 1)
[/CODE]
If you want the literal text ``[/CODE]`` in a code block then it must be entered as ``[\/CODE]``
to ensure that the FFML parser doesn't interpret it as the end of the code block. The ``'\'``
character is removed.
[*][B]Bulleted lists[/B], using BBCODE tags. Surround the list with ``[LIST]`` and
``[/LIST]``. List items are indicated with ``[*]``. All of the tags must be
first on a line. Bulleted lists can be nested and can contain other FFML
elements.

Example: a two bullet list containing CODE blocks
[CODE]
[LIST]
[*]Return the HTML of the note attached to the tag `Fiction`:
[CODE]
program:
  get_note('tags', 'Fiction', '')
[\/CODE]
[*]Return the plain text of the note attached to the author `Isaac Asimov`:
[CODE]
program:
  get_note('authors', 'Isaac Asimov', 1)
[\/CODE]
[/LIST]
[/CODE]
[*][B]End of summary marker[/B]. A summary is generated from the first characters of
the documentation. The summary includes text up to a \[\/] tag. There is no
opening tag because the summary starts at the first character. If there is
no \[\/] tag then all the document is used for the summary. The \[\/] tag
is removed, not replaced with white space or any other character.
[*][B]Escaped character[/B]: precede the character with a backslash. This is useful
to escape tags. For example to make the \[CODE] tag not a tag, use \\\[CODE].
Escaping characters doesn't work in `Inline program code text` or
`Example program code text blocks`.
[/LIST]
Note: HTML output contains no CSS and does not start with a tag such as <DIV> or <P>.
'''


if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    d = GeneralInformationDialog()
    d.exec()
    del d
    del app
