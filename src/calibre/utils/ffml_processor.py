#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from enum import IntEnum, auto, unique

from calibre import prepare_string_for_xml

# This must be something that will never naturally occur in documentation
MARKUP_ERROR = '*' + _('Template documentation markup error') + '*:'

@unique
class NodeKinds(IntEnum):

    @staticmethod
    def _generate_next_value_(name, start, count, last_values):
        return -(count + 1)

    DOCUMENT    = auto()
    BLANK_LINE  = auto()
    BOLD_TEXT   = auto()
    CHARACTER   = auto()
    CODE_TEXT   = auto()
    CODE_BLOCK  = auto()
    END_LIST    = auto()
    ERROR_TEXT  = auto()
    GUI_LABEL   = auto()
    ITALIC_TEXT = auto()
    LIST        = auto()
    LIST_ITEM   = auto()
    REF         = auto()
    END_SUMMARY = auto()
    TEXT        = auto()
    URL         = auto()


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
        return prepare_string_for_xml(self.text())


class BlankLineNode(Node):

    def __init__(self):
        super().__init__(NodeKinds.BLANK_LINE)


class BoldTextNode(Node):

    def __init__(self, text):
        super().__init__(NodeKinds.BOLD_TEXT)
        self._text = text


class CharacterNode(Node):

    def __init__(self, character):
        super().__init__(NodeKinds.CHARACTER)
        self._text = character


class CodeBlock(Node):

    def __init__(self, code_text):
        super().__init__(NodeKinds.CODE_BLOCK)
        self._text = code_text


class CodeText(Node):

    def __init__(self, code_text):
        super().__init__(NodeKinds.CODE_TEXT)
        self._text = code_text


class DocumentNode(Node):

    def __init__(self):
        super().__init__(NodeKinds.DOCUMENT)
        self._children = []


class EndSummaryNode(Node):

    def __init__(self):
        super().__init__(NodeKinds.END_SUMMARY)


class ErrorTextNode(Node):
    '''
    This is for internal use only. There is no FFML support to generate this node.
    '''

    def __init__(self, text):
        super().__init__(NodeKinds.ERROR_TEXT)
        self._text = text


class GuiLabelNode(Node):

    def __init__(self, text):
        super().__init__(NodeKinds.GUI_LABEL)
        self._text = text


class ItalicTextNode(Node):

    def __init__(self, text):
        super().__init__(NodeKinds.ITALIC_TEXT)
        self._text = text


class ListItemNode(Node):

    def __init__(self):
        super().__init__(NodeKinds.LIST_ITEM)


class ListNode(Node):

    def __init__(self):
        super().__init__(NodeKinds.LIST)


class RefNode(Node):

    def __init__(self, text):
        super().__init__(NodeKinds.REF)
        self._text = text


class TextNode(Node):

    def __init__(self, text):
        super().__init__(NodeKinds.TEXT)
        self._text = text


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



class FFMLProcessor:
    r"""
    This class is parser for the Formatter Function Markup Language (FFML). It
    provides output methods for RST and HTML.

    FFML is a basic markup language used to document formatter functions. It is
    based on a combination of RST used by sphinx and BBCODE used by many
    bulletin board systems such as MobileRead. You can see the documentation
    (in FFML) in the file gui2.dialogs.template_general_info.py. A formatted
    version is available by:
    - pushing the "General information" button in the Template tester
    - pushing the "FFML documentation" button in the "Formatter function
      documentation editor". How to access the editor is described in "General
      information" dialog mentioned above.
    """

# ====== API ======

    def print_node_tree(self, node, indent=0):
        """
        Pretty print a Formatter Function Markup Language (FFML) parse tree.

        :param node:   The root of the tree you want printed.
        :param indent: The indent level of the tree. The outermost root should
                       have an indent of zero.
        """
        if node.node_kind() in (NodeKinds.TEXT, NodeKinds.CODE_TEXT, NodeKinds.CHARACTER,
                                NodeKinds.CODE_BLOCK, NodeKinds.ITALIC_TEXT,
                                NodeKinds.GUI_LABEL, NodeKinds.BOLD_TEXT):
            print(f'{" " * indent}{node.node_kind().name}:{node.text()}')
        elif node.node_kind() == NodeKinds.URL:
            print(f'{" " * indent}URL: label={node.label()}, URL={node.url()}')
        else:
            print(f'{" " * indent}{node.node_kind().name}')
        for n in node.children():
            self.print_node_tree(n, indent+1)

    def parse_document(self, doc, name, safe=True):
        """
        Given a Formatter Function Markup Language (FFML) document, return
        a parse tree for that document.

        :param doc:   the document in FFML.
        :param name:  the name of the document, used for generating errors. This
                      is usually the name of the function.
        :param safe:  if true, do not propagate exceptions. Instead attempt to
                      recover using the Engiish version as well as display an error.

        :return:       a parse tree for the document
        """
        def initialize(txt):
            self.input_line = 1
            self.input = txt
            self.input_pos = 0
            self.document_name = name
            return DocumentNode()

        def add_exception_text(node, exc, orig_txt=None):
            if node.children():
                node.add_child(BlankLineNode())
            if orig_txt is None:
                node.add_child(ErrorTextNode(
                    _('Showing the documentation in English because of the {} error:').format('FFML')))
                node.add_child(TextNode(' ' + str(exc)))
            else:
                node.add_child(ErrorTextNode(MARKUP_ERROR))
                node.add_child(TextNode(' ' + str(exc)))
                node.add_child(BlankLineNode())
                node.add_child(ErrorTextNode(_('Documentation containing the error:')))
                node.add_child(TextNode(orig_txt))
            return node

        if not doc:
            return DocumentNode()

        node = initialize(doc)
        if not safe:
            return self._parse_document(node)
        try:
            return self._parse_document(node)
        except ValueError as e:
            # Syntax error. Try the English doc if it exists
            if hasattr(doc, 'formatted_english'):
                node = initialize(doc.formatted_english)
                try:
                    tree = self._parse_document(node)
                    # No exception. Add a text node with the error to the
                    # English documentation.
                    return add_exception_text(tree, e)
                except ValueError:
                    pass
            # Either no English text or a syntax error in both cases. Return a
            # node with the error message and the offending text
            return add_exception_text(DocumentNode(), e, doc)

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
        if tree.node_kind() == NodeKinds.BOLD_TEXT:
            result += f'<b>{tree.escaped_text()}</b>'
        elif tree.node_kind() == NodeKinds.BLANK_LINE:
            result += '\n<br>\n<br>\n'
        elif tree.node_kind() == NodeKinds.CHARACTER:
            result += tree.text()
        elif tree.node_kind() == NodeKinds.CODE_TEXT:
            result += f'<code>{tree.escaped_text()}</code>'
        elif tree.node_kind() == NodeKinds.CODE_BLOCK:
            result += f'<pre style="margin-left:2em"><code>{tree.escaped_text().rstrip()}</code></pre>'
        elif tree.node_kind() == NodeKinds.END_SUMMARY:
            pass
        elif tree.node_kind() == NodeKinds.ERROR_TEXT:
            result += f'<span style="color:red"><strong>{tree.escaped_text()}</strong></span>'
        elif tree.node_kind() == NodeKinds.GUI_LABEL:
            result += f'<span style="font-family: Sans-Serif">{tree.escaped_text()}</span>'
        elif tree.node_kind() == NodeKinds.ITALIC_TEXT:
            result += f'<i>{tree.escaped_text()}</i>'
        elif tree.node_kind() == NodeKinds.LIST:
            result += '\n<ul>\n'
            for child in tree.children():
                result += '<li>\n'
                result += self.tree_to_html(child, depth=depth+1)
                result += '</li>\n'
            result += '</ul>\n'
        elif tree.node_kind() == NodeKinds.REF:
            result += f'<a href="ffdoc:{tree.text()}">{tree.text()}</a></a>'
        elif tree.node_kind() == NodeKinds.URL:
            result += f'<a href="{tree.escaped_url()}">{tree.escaped_label()}</a>'
        elif tree.node_kind() in (NodeKinds.DOCUMENT, NodeKinds.LIST_ITEM):
            for child in tree.children():
                result += self.tree_to_html(child, depth=depth+1)
        return result

    def document_to_html(self, document, name, safe=True):
        """
        Given a document in the Formatter Function Markup Language (FFML), return
        that document in HTML format.

        :param document: the text in FFML.
        :param name: the name of the document, used during error
                     processing. It is usually the name of the function.
        :param safe: if true, do not propagate exceptions. Instead attempt to
                     recover using the English version as well as display an error.

        :return: a string containing the HTML

        """
        tree = self.parse_document(document, name, safe=safe)
        return self.tree_to_html(tree, 0)

    def document_to_summary_html(self, document, name, safe=True):
        """
        Given a document in the Formatter Function Markup Language (FFML), return
        that document's summary in HTML format.

        :param document: the text in FFML.
        :param name: the name of the document, used during error
                     processing. It is usually the name of the function.
        :param safe: if true, do not propagate exceptions. Instead attempt to
                     recover using the English version as well as display an error.

        :return: a string containing the HTML

        """
        document = document.strip()
        sum_tag = document.find('[/]')
        if sum_tag > 0:
            document = document[0:sum_tag]
        fname = document[0:document.find('(')].lstrip('`')
        tree = self.parse_document(document, name, safe=safe)
        result = self.tree_to_html(tree, depth=0)
        paren = result.find('(')
        result = f'<a href="ffdoc:{fname}">{fname}</a>{result[paren:]}'
        return result

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

        def indent_text(txt):
            nonlocal result
            if not result:
                txt = txt.lstrip()
            elif result.endswith('\n'):
                txt = txt.lstrip()
                result += '  ' * indent
            result += txt.replace('\n', '  ' * indent)

        if result is None:
            result = '  ' * indent

        if tree.node_kind() == NodeKinds.BLANK_LINE:
            result += '\n\n'
        elif tree.node_kind() == NodeKinds.BOLD_TEXT:
            indent_text(f'**{tree.text()}**')
        elif tree.node_kind() == NodeKinds.CHARACTER:
            result += tree.text()
        elif tree.node_kind() == NodeKinds.CODE_BLOCK:
            result += f"\n\n{'  ' * indent}::\n\n"
            for line in tree.text().strip().split('\n'):
                result += f"{'  ' * (indent+1)}{line}\n"
            result += '\n'
        elif tree.node_kind() == NodeKinds.CODE_TEXT:
            indent_text(f'``{tree.text()}``')
        elif tree.node_kind() == NodeKinds.END_SUMMARY:
            pass
        elif tree.node_kind() == NodeKinds.ERROR_TEXT:
            indent_text(f'**{tree.text()}**')
        elif tree.node_kind() == NodeKinds.GUI_LABEL:
            indent_text(f':guilabel:`{tree.text()}`')
        elif tree.node_kind() == NodeKinds.ITALIC_TEXT:
            indent_text(f'`{tree.text()}`')
        elif tree.node_kind() == NodeKinds.LIST:
            result += '\n\n'
            for child in tree.children():
                result += f"{'  ' * (indent)}* "
                result = self.tree_to_rst(child, indent+1, result=result)
                result += '\n'
            result += '\n'
        elif tree.node_kind() == NodeKinds.REF:
            if (rname := tree.text()).endswith('()'):
                rname = rname[:-2]
            indent_text(f':ref:`{rname}() <ff_{rname}>`')
        elif tree.node_kind() == NodeKinds.TEXT:
            indent_text(tree.text())
        elif tree.node_kind() == NodeKinds.URL:
            indent_text(f'`{tree.label()} <{tree.url()}>`_')
        elif tree.node_kind() in (NodeKinds.DOCUMENT, NodeKinds.LIST_ITEM):
            for child in tree.children():
                result = self.tree_to_rst(child, indent, result=result)
        return result

    def document_to_rst(self, document, name, indent=0, prefix=None, safe=True):
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
        :param safe:     if true, do not propagate exceptions. Instead attempt to
                         recover using the English version as well as display an error.

        :return: a string containing the RST text

        """
        doc = self.tree_to_rst(self.parse_document(document, name, safe=safe), indent)
        if prefix is not None:
            doc = prefix + doc.lstrip('  ' * indent)
        return doc

    def document_to_summary_rst(self, document, name, indent=0, prefix=None, safe=True):
        """
        Given a document in the Formatter Function Markup Language (FFML), return
        that document's summary in RST (sphinx reStructuredText) format.

        :param document: the text in FFML.
        :param name:     the name of the document, used during error
                         processing. It is usually the name of the function.
        :param indent:   the indenting level of the items in the tree. This is
                         usually zero, but can be greater than zero if you want
                         the RST output indented.
        :param prefix:   string. if supplied, this string replaces the indent
                         on the first line of the output. This permits specifying
                         an RST block, for example a bullet list
        :param safe:     if true, do not propagate exceptions. Instead attempt to
                         recover using the English version as well as display an error.

        :return: a string containing the RST text

        """
        document = document.strip()
        sum_tag = document.find('[/]')
        if sum_tag > 0:
            document = document[0:sum_tag]
        fname = document[0:document.find('(')].lstrip('`')
        doc = self.tree_to_rst(self.parse_document(document, name, safe=safe), indent)
        lparen = doc.find('(')
        doc = f':ref:`ff_{fname}`\\ ``{doc[lparen:]}'
        if prefix is not None:
            doc = prefix + doc.lstrip('  ' * indent)
        return doc

# ============== Internal methods =================

    keywords = {'``':           NodeKinds.CODE_TEXT, # must be before '`'
                '`':            NodeKinds.ITALIC_TEXT,
                '[B]':          NodeKinds.BOLD_TEXT,
                '[CODE]':       NodeKinds.CODE_BLOCK,
                '[/]':          NodeKinds.END_SUMMARY,
                ':guilabel:':   NodeKinds.GUI_LABEL,
                '[LIST]':       NodeKinds.LIST,
                '[/LIST]':      NodeKinds.END_LIST,
                ':ref:':        NodeKinds.REF,
                '[URL':         NodeKinds.URL,
                '[*]':          NodeKinds.LIST_ITEM,
                '\n\n':         NodeKinds.BLANK_LINE,
                '\\':           NodeKinds.CHARACTER
            }

    def __init__(self):
        self.document = DocumentNode()
        self.input = None
        self.input_pos = 0

    def error(self, message):
        raise ValueError(f'{message} on line {self.input_line} in "{self.document_name}"')

    def find(self, for_what):
        p = self.input.find(for_what, self.input_pos)
        if p < 0:
            return -1
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

    def get_bold_text(self):
        self.move_pos(len('[B]'))
        end = self.find('[/B]')
        if end < 0:
            self.error('Missing closing "[/B]" for bold')
        node = BoldTextNode(self.text_to(end))
        self.move_pos(end + len('[/B]'))
        return node

    def get_character(self):
        self.move_pos(1)
        node = CharacterNode(self.text_to(1))
        self.move_pos(1)
        return node

    def get_code_block(self):
        self.move_pos(len('[CODE]'))
        if self.text_to(1) == '\n':
            self.move_pos(1)
        end = self.find('[/CODE]')
        if end < 0:
            self.error('Missing [/CODE] for block')
        node = CodeBlock(self.text_to(end).replace(r'[\/CODE]', '[/CODE]'))
        self.move_pos(end + len('[/CODE]'))
        if self.text_to(1) == '\n':
            self.move_pos(1)
        return node

    def get_code_text(self):
        self.move_pos(len('``'))
        end = self.find('``')
        if end < 0:
            self.error('Missing closing "``" for CODE_TEXT')
        node = CodeText(self.text_to(end).rstrip(' '))
        self.move_pos(end + len('``'))
        return node

    def get_gui_label(self):
        self.move_pos(len(':guilabel:`'))
        end = self.find('`')
        if end < 0:
            self.error('Missing ` (backquote) for :guilabel:')
        node = GuiLabelNode(self.text_to_no_newline(end, 'GUI_LABEL (:guilabel:`)'))
        self.move_pos(end + len('`'))
        return node

    def get_italic_text(self):
        self.move_pos(1)
        end = self.find('`')
        if end < 0:
            self.error('Missing closing "`" for italics')
        node = ItalicTextNode(self.text_to(end))
        self.move_pos(end + 1)
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

    def get_ref(self):
        self.move_pos(len(':ref:`'))
        end = self.find('`')
        if end < 0:
            self.error('Missing ` (backquote) for :ref:')
        node = RefNode(self.text_to_no_newline(end, 'REF (:ref:`)'))
        self.move_pos(end + len('`'))
        return node

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
            elif p == NodeKinds.BLANK_LINE:
                parent.add_child(BlankLineNode())
                self.move_pos(2)
            elif p == NodeKinds.BOLD_TEXT:
                parent.add_child(self.get_bold_text())
            elif p == NodeKinds.CHARACTER:
                parent.add_child(self.get_character())
            elif p == NodeKinds.CODE_TEXT:
                parent.add_child(self.get_code_text())
            elif p == NodeKinds.CODE_BLOCK:
                parent.add_child(self.get_code_block())
            elif p == NodeKinds.END_SUMMARY:
                parent.add_child(EndSummaryNode())
                self.move_pos(3)
            elif p == NodeKinds.GUI_LABEL:
                parent.add_child(self.get_gui_label())
            elif p == NodeKinds.ITALIC_TEXT:
                parent.add_child(self.get_italic_text())
            elif p == NodeKinds.LIST:
                parent.add_child(self.get_list())
            elif p == NodeKinds.LIST_ITEM:
                return parent
            elif p == NodeKinds.END_LIST:
                return parent
            elif p == NodeKinds.REF:
                parent.add_child(self.get_ref())
            elif p == NodeKinds.URL:
                parent.add_child(self.get_url())
            else:
                self.error(f'Fatal parse error with node type {p}')
            if self.at_end():
                break
        return parent
