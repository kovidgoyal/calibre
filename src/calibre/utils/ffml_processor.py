#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from enum import IntEnum

from calibre import prepare_string_for_xml


class NodeKinds(IntEnum):
    DOCUMENT    = -1
    CODE_TEXT   = -2
    CODE_BLOCK  = -3
    URL         = -4
    BLANK_LINE  = -5
    TEXT        = -6
    LIST        = -7
    END_LIST    = -8
    LIST_ITEM   = -9
    GUI_LABEL   = -10
    ITALIC_TEXT = -11


class Node:

    def __init__(self, node_kind: NodeKinds):
        self._node_kind = node_kind
        self._children = []

    def node_kind(self) -> NodeKinds:
        return self._node_kind

    def add_child(self, node):
        self._children.append(node)

    def children(self):
        return self._children

    def text(self):
        return self._text

    def escaped_text(self):
        return prepare_string_for_xml(self._text)


class DocumentNode(Node):

    def __init__(self):
        super().__init__(NodeKinds.DOCUMENT)
        self._children = []


class TextNode(Node):

    def __init__(self, text):
        super().__init__(NodeKinds.TEXT)
        self._text = text


class CodeBlock(Node):

    def __init__(self, code_text):
        super().__init__(NodeKinds.CODE_BLOCK)
        self._text = code_text


class CodeText(Node):

    def __init__(self, code_text):
        super().__init__(NodeKinds.CODE_TEXT)
        self._text = code_text


class BlankLineNode(Node):

    def __init__(self):
        super().__init__(NodeKinds.BLANK_LINE)


class UrlNode(Node):

    def __init__(self, label, url):
        super().__init__(NodeKinds.URL)
        self._label = label
        self._url = url

    def label(self):
        return self._label

    def escaped_label(self):
        return prepare_string_for_xml(self._label)

    def url(self):
        return self._url

    def escaped_url(self):
        return prepare_string_for_xml(self._url)


class ListNode(Node):

    def __init__(self):
        super().__init__(NodeKinds.LIST)


class ListItemNode(Node):

    def __init__(self):
        super().__init__(NodeKinds.LIST_ITEM)


class ItalicTextNode(Node):

    def __init__(self, text):
        super().__init__(NodeKinds.ITALIC_TEXT)
        self._text = text


class GuiLabelNode(Node):

    def __init__(self, text):
        super().__init__(NodeKinds.GUI_LABEL)
        self._text = text



class FFMLProcessor:
    """
    This class is parser for the Formatter Function Markup Language (FFML). It
    provides output methods for RST and HTML.

    FFML is a basic markup language used to document formatter functions. It is
    based on a combination of RST used by sphinx and BBCODE used by many
    bulletin board systems such as MobileRead. It provides a way to specify:

    - inline program code text: surround this text with `` as in ``foo``.

    - italic text: surround this text with `, as in `foo`.

    - text intended to reference a calibre GUI action. This uses RST syntax.
      Example: :guilabel:`Preferences->Advanced->Template functions`

    - empty lines, indicated by two newlines in a row. A visible empty line
      in the FFMC will become an empty line in the output.

    - URLs. The syntax is similar to BBCODE: [URL href="http..."]Link text[/URL].
      Example: [URL href="https://en.wikipedia.org/wiki/ISO_8601"]ISO[/URL]

    - example program code text blocks. Surround the code block with [CODE]
      and [/CODE] tags. These tags must be first on a line. Example:
      [CODE]
      program:
          get_note('authors', 'Isaac Asimov', 1)
      [/CODE]

    - bulleted lists, using BBCODE tags. Surround the list with [LIST] and
      [/LIST]. List items are indicated with [*]. All of the tags must be
      first on a line. Bulleted lists can be nested and can contain other FFML
      elements. Example: a two bullet list containing CODE blocks
      [LIST]
      [*]Return the HTML of the note attached to the tag `Fiction`:
      [CODE]
      program:
          get_note('tags', 'Fiction', '')
      [/CODE]
      [*]Return the plain text of the note attached to the author `Isaac Asimov`:
      [CODE]
      program:
          get_note('authors', 'Isaac Asimov', 1)
      [/CODE]
      [/LIST]

    HTML output contains no CSS and does not start with a tag such as <DIV> or <P>.

    RST output is not indented.

    API example: generate documents for all builtin formatter functions
    --------------------
    from calibre.utils.ffml_processor import FFMLProcessor
    from calibre.utils.formatter_functions import formatter_functions
    from calibre.db.legacy import LibraryDatabase

    # We need this to load the formatter functions
    db = LibraryDatabase('<path to some library>')

    ffml = FFMLProcessor()
    funcs = formatter_functions().get_builtins()

    with open('all_docs.html', 'w') as w:
        for name in sorted(funcs):
            w.write(f'\n<h2>{name}</h2>\n')
            w.write(ffml.document_to_html(funcs[name].doc, name))

    with open('all_docs.rst', 'w') as w:
        for name in sorted(funcs):
            w.write(f"\n\n{name}\n{'^'*len(name)}\n\n")
            w.write(ffml.document_to_rst(funcs[name].doc, name))
    --------------------
    """

# ====== API ======

    def print_node_tree(self, node, indent=0):
        """
        Pretty print a Formatter Function Markup Language (FFML) parse tree.

        :param node:   The root of the tree you want printed.
        :param indent: The indent level of the tree. The outermost root should
                       have an indent of zero.
        """
        if node.node_kind() in (NodeKinds.TEXT, NodeKinds.CODE_TEXT,
                                NodeKinds.CODE_BLOCK, NodeKinds.ITALIC_TEXT,
                                NodeKinds.GUI_LABEL):
            print(f'{" " * indent}{node.node_kind().name}:{node.text()}')
        elif node.node_kind() == NodeKinds.URL:
            print(f'{" " * indent}URL: label={node.label()}, URL={node.url()}')
        else:
            print(f'{" " * indent}{node.node_kind().name}')
        for n in node.children():
            self.print_node_tree(n, indent+1)

    def parse_document(self, doc, name):
        """
        Given a Formatter Function Markup Language (FFML) document, return
        a parse tree for that document.

        :param doc:   the document in FFML.
        :param name:  the name of the document, used for generating errors. This
                      is usually the name of the function.

        :return:       a parse tree for the document
        """
        self.input = doc
        self.input_pos = 0
        self.document_name = name

        node = DocumentNode()
        return self._parse_document(node)

    def tree_to_html(self, tree, depth=0):
        """
        Given a Formatter Function Markup Language (FFML) parse tree, return
        a string containing the HTML for that tree.

        :param tree:   the parsed FFML.
        :param depth:  the recursion level. This is used for debugging.

        :return:       a string containing the HTML text
        """
        result = ''
        if tree.node_kind() == NodeKinds.TEXT:
            result += tree.escaped_text()
        elif tree.node_kind() == NodeKinds.CODE_TEXT:
            result += f'<code>{tree.escaped_text()}</code>'
        elif tree.node_kind() == NodeKinds.CODE_BLOCK:
            result += f'<pre style="margin-left:2em"><code>{tree.escaped_text()}</code></pre>'
        elif tree.node_kind() == NodeKinds.ITALIC_TEXT:
            result += f'<i>{tree.escaped_text()}</i>'
        elif tree.node_kind() == NodeKinds.GUI_LABEL:
            result += f'<span style="font-family: Sans-Serif">{tree.escaped_text()}</span>'
        elif tree.node_kind() == NodeKinds.BLANK_LINE:
            result += '\n<br>\n<br>\n'
        elif tree.node_kind() == NodeKinds.URL:
            result += f'<a href="{tree.escaped_url()}">{tree.escaped_label()}</a>'
        elif tree.node_kind() == NodeKinds.LIST:
            result += '\n<ul>\n'
            for child in tree.children():
                result += '<li>\n'
                result += self.tree_to_html(child, depth+1)
                result += '</li>\n'
            result += '</ul>\n'
        elif tree.node_kind() in (NodeKinds.DOCUMENT, NodeKinds.LIST_ITEM):
            for child in tree.children():
                result += self.tree_to_html(child, depth+1)
        return result

    def document_to_html(self, document, name):
        """
        Given a document in the Formatter Function Markup Language (FFML), return
        that document in HTML format.

        :param document: the text in FFML.
        :param name: the name of the document, used during error
                     processing. It is usually the name of the function.

        :return: a string containing the HTML

        """
        tree = self.parse_document(document, name)
        return self.tree_to_html(tree, 0)

    def tree_to_rst(self, tree, indent, result=None):
        """
        Given a Formatter Function Markup Language (FFML) parse tree, return
        a string containing the RST (sphinx reStructuredText) for that tree.

        :param tree:   the parsed FFML.
        :param indent: the indenting level of the items in the tree. This is
                       usually zero, but can be greater than zero if you want
                       the RST output indented.

        :return:       a string containing the RST text
        """
        if result is None:
            result = '  ' * indent
        if tree.node_kind() == NodeKinds.TEXT:
            txt = tree.text()
            if not result:
                txt = txt.lstrip()
            elif result.endswith('\n'):
                txt = txt.lstrip()
                result += '  ' * indent
            result += txt
        elif tree.node_kind() == NodeKinds.CODE_TEXT:
            result += f'``{tree.text()}``'
        elif tree.node_kind() == NodeKinds.GUI_LABEL:
            result += f':guilabel:`{tree.text()}`'
        elif tree.node_kind() == NodeKinds.CODE_BLOCK:
            result += f"\n\n{'  ' * indent}::\n\n"
            for line in tree.text().strip().split('\n'):
                result += f"{'  ' * (indent+1)}{line}\n"
            result += '\n'
        elif tree.node_kind() == NodeKinds.BLANK_LINE:
            result += '\n\n'
        elif tree.node_kind() == NodeKinds.ITALIC_TEXT:
            result += f'`{tree.text()}`'
        elif tree.node_kind() == NodeKinds.URL:
            result += f'`{tree.label()} <{tree.url()}>`_'
        elif tree.node_kind() == NodeKinds.LIST:
            result += '\n\n'
            for child in tree.children():
                result += f"{'  ' * (indent)}* "
                result = self.tree_to_rst(child, indent+1, result)
                result += '\n'
            result += '\n'
        elif tree.node_kind() in (NodeKinds.DOCUMENT, NodeKinds.LIST_ITEM):
            for child in tree.children():
                result = self.tree_to_rst(child, indent, result)
        return result

    def document_to_rst(self, document, name, indent=0, prefix=None):
        """
        Given a document in the Formatter Function Markup Language (FFML), return
        that document in RST (sphinx reStructuredText) format.

        :param document: the text in FFML.
        :param name:     the name of the document, used during error
                         processing. It is usually the name of the function.
        :param indent:   the indenting level of the items in the tree. This is
                         usually zero, but can be greater than zero if you want
                         the RST output indented.
        :param prefix:   string. if supplied, this string replaces the indent
                         on the first line of the output. This permits specifying
                         an RST block, for example a bullet list

        :return: a string containing the RST text

        """
        doc = self.tree_to_rst(self.parse_document(document, name), indent)
        if prefix is not None:
            doc = prefix + doc.lstrip(' ')
        return doc

# ============== Internal methods =================

    keywords = {'``':           NodeKinds.CODE_TEXT, # must be before '`'
                '`':            NodeKinds.ITALIC_TEXT,
                ':guilabel:':   NodeKinds.GUI_LABEL,
                '[CODE]':       NodeKinds.CODE_BLOCK,
                '[URL':         NodeKinds.URL,
                '[LIST]':       NodeKinds.LIST,
                '[/LIST]':      NodeKinds.END_LIST,
                '[*]':          NodeKinds.LIST_ITEM,
                '\n\n':         NodeKinds.BLANK_LINE
            }

    def __init__(self):
        self.document = DocumentNode()
        self.input = None
        self.input_pos = 0
        self.input_line = 1

    def error(self, message):
        raise ValueError(f'{message} on line {self.input_line} in "{self.document_name}"')

    def find(self, for_what):
        p = self.input.find(for_what, self.input_pos)
        return -1 if p < 0 else p - self.input_pos

    def move_pos(self, to_where):
        for c in self.input[self.input_pos:self.input_pos+to_where]:
            if c == '\n':
                self.input_line += 1
        self.input_pos += to_where

    def at_end(self):
        return self.input_pos >= len(self.input)

    def text_to(self, end):
        return self.input[self.input_pos:self.input_pos+end]

    def text_contains_newline(self, txt):
        return '\n' in txt

    def text_to_no_newline(self, end, block_name):
        txt = self.input[self.input_pos:self.input_pos+end]
        if self.text_contains_newline(txt):
            self.error(f'Newline unexpected in {block_name}')
        return txt

    def startswith(self, txt):
        return self.input.startswith(txt, self.input_pos)

    def find_one_of(self):
        positions = []
        for s in self.keywords:
            p = self.find(s)
            if p == 0:
                return self.keywords[s]
            positions.append(self.find(s))
        positions = list(filter(lambda x: x >= 0, positions))
        if positions:
            return min(positions)
        return len(self.input)

    def get_code_text(self):
        self.move_pos(len('``'))
        end = self.find('``')
        if end < 0:
            self.error('Missing closing "``" for CODE_TEXT')
        node = CodeText(self.text_to(end))
        self.move_pos(end + len('``'))
        return node

    def get_italic_text(self):
        self.move_pos(1)
        end = self.find('`')
        if end < 0:
            self.error('Missing closing "`" for italics')
        node = ItalicTextNode(self.text_to(end))
        self.move_pos(end + 1)
        return node

    def get_gui_label(self):
        self.move_pos(len(':guilabel:`'))
        end = self.find('`')
        if end < 0:
            self.error('Missing ` (backquote) for :guilabel:')
        node = GuiLabelNode(self.text_to_no_newline(end, 'GUI_LABEL (:guilabel:`)'))
        self.move_pos(end + len('`'))
        return node

    def get_code_block(self):
        self.move_pos(len('[CODE]\n'))
        end = self.find('[/CODE]')
        if end < 0:
            self.error('Missing [/CODE] for block')
        node = CodeBlock(self.text_to(end))
        self.move_pos(end + len('[/CODE]'))
        if self.text_to(1) == '\n':
            self.move_pos(1)
        return node

    def get_list(self):
        self.move_pos(len('[LIST]\n'))
        list_node = ListNode()
        while True:
            if self.startswith('[/LIST]'):
                break
            if not self.startswith('[*]'):
                self.error(f'Missing [*] in list near text:"{self.text_to(10)}"')
            self.move_pos(len('[*]'))
            node = self._parse_document(ListItemNode())
            list_node.add_child(node)
        self.move_pos(len('[/LIST]'))
        if self.text_to(1) == '\n':
            self.move_pos(1)
        return list_node

    def get_url(self):
        self.move_pos(len('[URL'))
        hp = self.find('href="')
        if hp < 0:
            self.error(f'Missing href=" near text {self.text_to(10)}')
        self.move_pos(hp + len('href="'))
        close_quote = self.find('"]')
        if close_quote < 0:
            self.error(f'Missing closing "> for URL near text:"{self.text_to(10)}"')
        href = self.text_to_no_newline(close_quote, 'URL href')
        self.move_pos(close_quote + len('"]'))
        lp = self.find('[/URL]')
        if lp < 0:
            self.error(f'Missing closing [/URL] near text {self.text_to(10)}')
        label = self.text_to(lp).strip()
        label = label.replace('\n', ' ')
        node = UrlNode(label, href)
        self.move_pos(lp + len('[/URL]'))
        return node

    def _parse_document(self, parent):
        while True:
            p = self.find_one_of()
            if p > 0:
                txt = self.text_to(p).replace('\n', ' ')
                parent.add_child(TextNode(txt))
                self.move_pos(p)
            elif p == NodeKinds.CODE_TEXT:
                parent.add_child(self.get_code_text())
            elif p == NodeKinds.CODE_BLOCK:
                parent.add_child(self.get_code_block())
            elif p == NodeKinds.LIST:
                parent.add_child(self.get_list())
            elif p == NodeKinds.LIST_ITEM:
                return parent
            elif p == NodeKinds.END_LIST:
                return parent
            elif p == NodeKinds.BLANK_LINE:
                parent.add_child(BlankLineNode())
                self.move_pos(2)
            elif p == NodeKinds.ITALIC_TEXT:
                parent.add_child(self.get_italic_text())
            elif p == NodeKinds.GUI_LABEL:
                parent.add_child(self.get_gui_label())
            elif p == NodeKinds.URL:
                parent.add_child(self.get_url())
            else:
                self.move_pos(p+1)
            if self.at_end():
                break
        return parent
