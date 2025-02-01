__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'


from lxml import etree


class InlineClass(etree.XSLTExtension):

    FMTS = ('italics', 'bold', 'strike-through', 'small-caps')

    def __init__(self, log):
        etree.XSLTExtension.__init__(self)
        self.log = log
        self.font_sizes = []
        self.colors = []

    def execute(self, context, self_node, input_node, output_parent):
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

        output_parent.text = ' '.join(classes)
