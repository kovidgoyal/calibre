#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Font size rationalization. See :function:`relativize`.
'''

import logging, re, operator, functools, collections, unittest, copy, sys
from xml.dom import SyntaxErr

from lxml.cssselect import CSSSelector
from lxml import etree
from lxml.html import HtmlElement

from calibre.ebooks.html import fromstring
from calibre.ebooks.epub import rules
from cssutils import CSSParser

num           = r'[-]?\d+|[-]?\d*\.\d+'
length        = r'(?P<zero>0)|(?P<num>{num})(?P<unit>%|em|ex|px|in|cm|mm|pt|pc)'.replace('{num}', num)
absolute_size = r'(?P<abs>(x?x-)?(small|large)|medium)'
relative_size = r'(?P<rel>smaller|larger)'

font_size_pat   = re.compile('|'.join((relative_size, absolute_size, length)), re.I)
line_height_pat = re.compile(r'({num})(px|in|cm|mm|pt|pc)'.replace('{num}', num))  

PTU = {
       'in' : 72.,
       'cm' : 72/2.54,
       'mm' : 72/25.4,
       'pt' : 1.0,
       'pc' : 1/12.,
       }

DEFAULT_FONT_SIZE = 12

class Rationalizer(object):
    
    @classmethod
    def specificity(cls, s):
        '''Map CSS specificity tuple to a single integer'''
        return sum([10**(4-i) + x for i,x in enumerate(s)]) 
        
    @classmethod
    def compute_font_size(cls, elem):
        '''
        Calculate the effective font size of an element traversing its ancestors as far as
        neccessary.
        '''
        cfs = elem.computed_font_size
        if cfs is not None:
            return
        sfs = elem.specified_font_size
        if callable(sfs):
            parent = elem.getparent()
            cls.compute_font_size(parent)
            elem.computed_font_size = sfs(parent.computed_font_size)
        else:
            elem.computed_font_size = sfs
        
    @classmethod
    def calculate_font_size(cls, style):
        'Return font size in pts from style object. For relative units returns a callable'
        match = font_size_pat.search(style.font)
        fs = ''
        if match:
            fs = match.group()
        if style.fontSize:
            fs = style.fontSize
            
        match = font_size_pat.search(fs)
        if match is None:
            return None
        match = match.groupdict()
        unit = match.get('unit', '')
        if unit: unit = unit.lower()
        if unit in PTU.keys():
            return PTU[unit] * float(match['num'])
        if unit in ('em', 'ex'):
            return functools.partial(operator.mul, float(match['num']))
        if unit == '%':
            return functools.partial(operator.mul, float(match['num'])/100.)
        abs = match.get('abs', '')
        if abs: abs = abs.lower()
        if abs:
            x = (1.2)**(abs.count('x') * (-1 if 'small' in abs else 1))
            return 12 * x
        if match.get('zero', False):
            return 0.
        return functools.partial(operator.mul, 1.2) if 'larger' in fs.lower() else functools.partial(operator.mul, 0.8) 
        
    @classmethod
    def resolve_rules(cls, stylesheets):
        for sheet in stylesheets:
            if hasattr(sheet, 'fs_rules'):
                continue
            sheet.fs_rules = []
            sheet.lh_rules = []
            for r in sheet:
                if r.type == r.STYLE_RULE:
                    font_size = cls.calculate_font_size(r.style)
                    if font_size is not None:
                        for s in r.selectorList:
                            sheet.fs_rules.append([CSSSelector(s.selectorText), font_size])
                    orig = line_height_pat.search(r.style.lineHeight) 
                    if orig is not None:
                        for s in r.selectorList:
                            sheet.lh_rules.append([CSSSelector(s.selectorText), float(orig.group(1)) * PTU[orig.group(2).lower()]])
    
        
    @classmethod
    def apply_font_size_rules(cls, stylesheets, root):
        'Add a ``specified_font_size`` attribute to every element that has a specified font size'
        cls.resolve_rules(stylesheets)
        for sheet in stylesheets:
            for selector, font_size in sheet.fs_rules:
                elems = selector(root)
                for elem in elems:
                    elem.specified_font_size = font_size
    
    @classmethod
    def remove_font_size_information(cls, stylesheets):
        for r in rules(stylesheets):
            r.style.removeProperty('font-size')
            try:
                new = font_size_pat.sub('', r.style.font).strip()
                if new:
                    r.style.font = new
                else:
                    r.style.removeProperty('font')
            except SyntaxErr:
                r.style.removeProperty('font')
            if line_height_pat.search(r.style.lineHeight) is not None:
                r.style.removeProperty('line-height')
    
    @classmethod
    def compute_font_sizes(cls, root, stylesheets, base=12):
        stylesheets = [s for s in stylesheets if hasattr(s, 'cssText')]
        cls.apply_font_size_rules(stylesheets, root)
        
        # Compute the effective font size of all tags
        root.computed_font_size = DEFAULT_FONT_SIZE
        for elem in root.iter(etree.Element):
            cls.compute_font_size(elem)
        
        extra_css = {}
        if base > 0:
            # Calculate the "base" (i.e. most common) font size
            font_sizes = collections.defaultdict(lambda : 0)
            body = root.xpath('//body')[0]
            IGNORE = ('h1', 'h2', 'h3', 'h4', 'h5', 'h6')
            for elem in body.iter(etree.Element):
                if elem.tag not in IGNORE:
                    t = getattr(elem, 'text', '')
                    if t: t = t.strip()
                    if t:
                        font_sizes[elem.computed_font_size] += len(t)
                    
                t = getattr(elem, 'tail', '')
                if t: t = t.strip()
                if t:
                    parent = elem.getparent()
                    if parent.tag not in IGNORE:
                        font_sizes[parent.computed_font_size] += len(t)
                
            try:
                most_common = max(font_sizes.items(), key=operator.itemgetter(1))[0]
                scale = base/most_common if most_common > 0 else 1.
            except ValueError:
                scale = 1.
            
            # rescale absolute line-heights
            counter = 0
            for sheet in stylesheets:
                for selector, lh in sheet.lh_rules:
                    for elem in selector(root):
                        elem.set('id', elem.get('id', 'cfs_%d'%counter))
                        counter += 1
                        if not extra_css.has_key(elem.get('id')):
                            extra_css[elem.get('id')] = []
                        extra_css[elem.get('id')].append('line-height:%fpt'%(lh*scale))
            
        
            
            # Rescale all computed font sizes
            for elem in body.iter(etree.Element):
                if isinstance(elem, HtmlElement):
                    elem.computed_font_size *= scale
        
        # Remove all font size specifications from the last stylesheet 
        cls.remove_font_size_information(stylesheets[-1:])
                    
        # Create the CSS to implement the rescaled font sizes
        for elem in body.iter(etree.Element):
            cfs, pcfs = map(operator.attrgetter('computed_font_size'), (elem, elem.getparent()))
            if abs(cfs-pcfs) > 1/12. and abs(pcfs) > 1/12.:
                elem.set('id', elem.get('id', 'cfs_%d'%counter))
                counter += 1
                if not extra_css.has_key(elem.get('id')):
                    extra_css[elem.get('id')] = []
                extra_css[elem.get('id')].append('font-size: %f%%'%(100*(cfs/pcfs)))
                
        css = CSSParser(loglevel=logging.ERROR).parseString('')
        for id, r in extra_css.items():
            css.add('#%s {%s}'%(id, ';'.join(r)))
        return css
    
    @classmethod
    def rationalize(cls, stylesheets, root, opts):
        logger     = logging.getLogger('html2epub')
        logger.info('\t\tRationalizing fonts...')
        extra_css = None
        if opts.base_font_size2 > 0:
            try:
                extra_css = cls.compute_font_sizes(root, stylesheets, base=opts.base_font_size2)
            except:
                logger.warning('Failed to rationalize font sizes.')
                if opts.verbose > 1:
                    logger.exception('')
            finally:
                root.remove_font_size_information()
        logger.debug('\t\tDone rationalizing')
        return extra_css

################################################################################
############## Testing
################################################################################

class FontTest(unittest.TestCase):
    
    def setUp(self):
        from calibre.ebooks.epub import config
        self.opts = config(defaults='').parse()
        self.html = '''
        <html>
            <head>
                <title>Test document</title>
            </head>
            <body>
                <div id="div1">
                <!-- A comment -->
                    <p id="p1">Some <b>text</b></p>
                </div>
                <p id="p2">Some other <span class="it">text</span>.</p>
                <p id="longest">The longest piece of single font size text in this entire file. Used to test resizing.</p>
            </body>
        </html> 
        '''
        self.root = fromstring(self.html)
        
    def do_test(self, css, base=DEFAULT_FONT_SIZE, scale=1):
        root1 = copy.deepcopy(self.root)
        root1.computed_font_size = DEFAULT_FONT_SIZE
        stylesheet = CSSParser(loglevel=logging.ERROR).parseString(css)
        stylesheet2 = Rationalizer.compute_font_sizes(root1, [stylesheet], base)
        root2 = copy.deepcopy(root1)
        root2.remove_font_size_information()
        root2.computed_font_size = DEFAULT_FONT_SIZE
        Rationalizer.apply_font_size_rules([stylesheet2], root2)
        for elem in root2.iter(etree.Element):
            Rationalizer.compute_font_size(elem)
        for e1, e2 in zip(root1.xpath('//body')[0].iter(etree.Element), root2.xpath('//body')[0].iter(etree.Element)):
            self.assertAlmostEqual(e1.computed_font_size, e2.computed_font_size, 
                msg='Computed font sizes for %s not equal. Original: %f Processed: %f'%\
                (root1.getroottree().getpath(e1), e1.computed_font_size, e2.computed_font_size))
        return stylesheet2.cssText
        
    def testStripping(self):
        'Test that any original entries are removed from the CSS'
        css = 'p { font: bold 10px italic smaller; font-size: x-large} \na { font-size: 0 }'
        css = CSSParser(loglevel=logging.ERROR).parseString(css)
        Rationalizer.compute_font_sizes(copy.deepcopy(self.root), [css])
        self.assertEqual(css.cssText.replace(' ', '').replace('\n', ''), 
                         'p{font:bolditalic}')
    
    def testIdentity(self):
        'Test that no unnecessary font size changes are made'
        extra_css = self.do_test('div {font-size:12pt} \nspan {font-size:100%}')
        self.assertEqual(extra_css.strip(), '')
        
    def testRelativization(self):
        'Test conversion of absolute to relative sizes'
        self.do_test('#p1 {font: 24pt} b {font: 12pt} .it {font: 48pt} #p2 {font: 100%}')
        
    def testResizing(self):
        'Test resizing of fonts'
        self.do_test('#longest {font: 24pt} .it {font:20pt; line-height:22pt}')
        

def suite():
    return unittest.TestLoader().loadTestsFromTestCase(FontTest)
    
def test():
    unittest.TextTestRunner(verbosity=2).run(suite())

if __name__ == '__main__':
    sys.exit(test())    
        