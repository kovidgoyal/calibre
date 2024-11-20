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

    def __init__(self, parent=None):
        super().__init__(title=_('Template function general information'), name='template_editor_gen_info_dialog',
                         default_buttons=QDialogButtonBox.StandardButton.Close, parent=parent)

    def setup_ui(self):
        l = QVBoxLayout(self)
        e = HTMLDisplay(self)
        l.addWidget(e)
        if iswindows:
            e.setDefaultStyleSheet('pre { font-family: "Segoe UI Mono", "Consolas", monospace; }')
        l.addWidget(self.bb)
        e.setHtml(FFMLProcessor().document_to_html(information, 'Template Information'))


information = r'''
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
[*]`Editor for asssting with template function documentation`

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
[*]The `Template Function Markup Language`

Format Function Markup Language (FFML) is a basic markup language used to
document formatter functions. It is based on a combination of RST used by sphinx
and BBCODE used by many bulletin board systems such as MobileRead. It provides a
way to specify:
[LIST]
[*]Inline program code text: surround this text with \`\` as in \`\`foo\`\`. Tags inside the text are ignored.
[*]Italic text: surround this text with \`. Example: \`foo\` produces `foo`.
[*]Bold text: surround this text with \[B]text\[\B] tags. Example: \[B]foo\[/B] produces [B]foo[/B].
[*]Text intended to reference a calibre GUI action. This uses RST syntax.\
  Example: \:guilabel\:\`Preferences->Advanced->Template functions\`. For HTML the produced text is in a different font, as in: :guilabel:`Some text`
[*]Empty lines, indicated by two newlines in a row. A visible empty line in the FFML
will become an empty line in the output.
[*]URLs. The syntax is similar to BBCODE: ``[URL href="http..."]Link text[/URL]``.\
  Example: ``[URL href="https://en.wikipedia.org/wiki/ISO_8601"]ISO[/URL]`` produces [URL href="https://en.wikipedia.org/wiki/ISO_8601"]ISO[/URL]
[*]Internal function reference links. These are links to formatter function
documentation. The syntax is the same as guilabel. Example: ``:ref:\`get_note\```.
The characters '()' are automatically added to the function name when
displayed. For HTML it generates the same as the inline program code text
operator (\`\`) with no link. Example: ``:ref:`add` `` produces ``add()``.
For RST it generates a ``:ref:`` reference that works only in an RST document
containing formatter function documentation. Example: ``:ref:\`get_note\```
generates \:ref\:\`get_note() <ff_get_note>\`
[*]Example program code text blocks. Surround the code block with ``[CODE]``
and ``[/CODE]`` tags. These tags must be first on a line. Example:
[CODE]
\[CODE]program:
    get_note('authors', 'Isaac Asimov', 1)
\[/CODE]
[/CODE]
produces
[CODE]
program:
    get_note('authors', 'Isaac Asimov', 1)[/CODE]

[*]Bulleted lists, using BBCODE tags. Surround the list with ``[LIST]`` and
``[/LIST]``. List items are indicated with ``[*]``. All of the tags must be
first on a line. Bulleted lists can be nested and can contain other FFML
elements.

Example: a two bullet list containing CODE blocks
[CODE]
\[LIST]
[*]Return the HTML of the note attached to the tag `Fiction`:
\[CODE]
program:
  get_note('tags', 'Fiction', '')
\[/CODE]
[*]Return the plain text of the note attached to the author `Isaac Asimov`:
\[CODE]
program:
  get_note('authors', 'Isaac Asimov', 1)
\[/CODE]
\[/LIST]
[/CODE]
[*]End of summary marker. A summary is generated from the first characters  of
the documentation. The summary includes text up to a \[/] tag. There is no
opening tag because the summary starts at the first character. If there is
no \[/] tag then all the document is used for the summary. The \[/] tag
is not replaced with white space or any other character.
[*]Escaped character: precede the character with a backslash. This is useful
to escape tags. For example to make the \[CODE] tag not a tag, use \\\[CODE].

[*]HTML output contains no CSS and does not start with a tag such as <DIV> or <P>.
[/LIST]
[/LIST]
'''


if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    d = GeneralInformationDialog()
    d.exec()
    del d
    del app
