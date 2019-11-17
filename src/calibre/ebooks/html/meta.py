

__license__ = 'GPL 3'
__copyright__ = '2010, Fabian Grassl <fg@jusmeum.de>'
__docformat__ = 'restructuredtext en'


class EasyMeta(object):

    def __init__(self, meta):
        self.meta = meta

    def __iter__(self):
        from calibre.ebooks.oeb.base import namespace, barename, DC11_NS
        meta = self.meta
        for item_name in meta.items:
            for item in meta[item_name]:
                if namespace(item.term) == DC11_NS:
                    yield {'name': barename(item.term), 'value': item.value}

    def __len__(self):
        count = 0
        for item in self:
            count = count+1
        return count

    def titles(self):
        for item in self.meta['title']:
            yield item.value

    def creators(self):
        for item in self.meta['creator']:
            yield item.value
