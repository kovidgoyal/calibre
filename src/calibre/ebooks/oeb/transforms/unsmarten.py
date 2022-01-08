__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from calibre.ebooks.oeb.base import OEB_DOCS, XPath, barename
from calibre.utils.unsmarten import unsmarten_text


class UnsmartenPunctuation:

    def __init__(self):
        self.html_tags = XPath('descendant::h:*')

    def unsmarten(self, root):
        for x in self.html_tags(root):
            if not barename(x.tag) == 'pre':
                if getattr(x, 'text', None):
                    x.text = unsmarten_text(x.text)
                if getattr(x, 'tail', None) and x.tail:
                    x.tail = unsmarten_text(x.tail)

    def __call__(self, oeb, context):
        bx = XPath('//h:body')
        for x in oeb.manifest.items:
            if x.media_type in OEB_DOCS:
                for body in bx(x.data):
                    self.unsmarten(body)
