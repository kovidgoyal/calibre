# License: GPLv3 Copyright: 2008, Kovid Goyal <kovid at kovidgoyal.net>

from typing import TYPE_CHECKING

from lxml import etree

if TYPE_CHECKING:
    from lxml.etree import _Element

    from calibre.utils.logging import Log


class InlineClass(etree.XSLTExtension):
    FMTS = ('italics', 'bold', 'strike-through', 'small-caps')

    def __init__(self, log: Log) -> None:
        etree.XSLTExtension.__init__(self)
        self.log = log
        self.font_sizes = []
        self.colors = []

    def execute(self, context: object, self_node: _Element, input_node: _Element, output_parent: _Element | None) -> None:
        classes = ['none']
        for x in self.FMTS:
            if input_node.get(x, None) == 'true':
                classes.append(x)
        # underlined is special
        if input_node.get('underlined', 'false') != 'false':
            classes.append('underlined')
        fs = input_node.get('font-size', False)
        if fs:
            if fs not in self.font_sizes:
                self.font_sizes.append(fs)
            classes.append(f'fs{self.font_sizes.index(fs)}')
        fc = input_node.get('font-color', False)
        if fc:
            if fc not in self.colors:
                self.colors.append(fc)
            classes.append(f'col{self.colors.index(fc)}')

        assert output_parent is not None  # always used inside an xsl:attribute in rtf.xsl
        output_parent.text = ' '.join(classes)
