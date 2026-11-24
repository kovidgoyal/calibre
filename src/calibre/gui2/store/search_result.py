# License: GPLv3 Copyright: 2011, John Schember <john@nachtimwald.com>

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from calibre.utils.browser import Browser


class SearchResult:
    DRM_LOCKED = 1
    DRM_UNLOCKED = 2
    DRM_UNKNOWN = 3

    # Set by the search results model
    cover_queued: bool

    def __init__(self) -> None:
        self.store_name = ''
        self.cover_url = ''
        self.cover_data: bytes | None = None
        self.title = ''
        self.author = ''
        self.price = ''
        self.detail_item = ''
        self.drm: int | None = None
        self.formats = ''
        # key = format in upper case.
        # value = url to download the file.
        self.downloads: dict[str, str] = {}
        self.affiliate = False
        self.plugin_author = ''
        self.create_browser: Callable[[], Browser] | None = None
        self.ebooks_com_api_url = ''

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SearchResult):
            return NotImplemented
        return self.title == other.title and self.author == other.author and self.store_name == other.store_name and self.formats == other.formats

    def __hash__(self) -> int:
        return hash((self.title, self.author, self.store_name, self.formats))

    def __str__(self) -> str:
        items = []
        for x in 'store_name title author price formats detail_item cover_url'.split():
            items.append(f'\t{x}={getattr(self, x)!r}')
        return 'SearchResult(\n{}\n)'.format('\n'.join(items))

    __repr__ = __str__
    __unicode__ = __str__
