# License: GPLv3 Copyright: 2010, Fabian Grassl <fg@jusmeum.de>

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

    from calibre.ebooks.oeb.base import Metadata


class EasyMeta:
    def __init__(self, meta: Metadata) -> None:
        self.meta = meta

    def __iter__(self) -> Iterator[dict[str, str]]:
        from calibre.ebooks.oeb.base import DC11_NS, barename, namespace

        meta = self.meta
        for item_name in meta.items:
            for item in meta[item_name]:
                if namespace(item.term) == DC11_NS:
                    yield {'name': barename(item.term), 'value': item.value}

    def __len__(self) -> int:
        count = 0
        for item in self:
            count = count + 1
        return count

    def titles(self) -> Iterator[str]:
        for item in self.meta['title']:
            yield item.value

    def creators(self) -> Iterator[str]:
        for item in self.meta['creator']:
            yield item.value
