#!/usr/bin/env python
# License: GPLv3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>

import json
from base64 import standard_b64encode
from itertools import count
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from qt.core import QWidget

    from calibre.gui2.ui import Main
    from calibre.utils.browser import Browser

counter = count()


class WebStoreDialog:
    def __init__(
        self,
        gui: Main,
        base_url: str,
        parent: QWidget | None = None,
        detail_url: str | None = None,
        create_browser: Callable[[], Browser] | None = None,
    ) -> None:
        self.id = next(counter)
        self.gui = gui
        self.base_url = base_url
        self.detail_url = detail_url
        self.window_title: str | None = None
        self.tags: str | None = None

    def setWindowTitle(self, title: str) -> None:
        self.window_title = title

    def set_tags(self, tags: str) -> None:
        self.tags = tags

    def exec(self) -> None:
        data = {
            'base_url': self.base_url,
            'detail_url': self.detail_url,
            'window_title': self.window_title,
            'tags': self.tags,
            'id': self.id,
        }
        data = json.dumps(data)
        if not isinstance(data, bytes):
            data = data.encode('utf-8')
        data = standard_b64encode(data)
        if isinstance(data, bytes):
            data = data.decode('ascii')
        args = ['store-dialog', data]
        self.gui.job_manager.launch_gui_app(args[0], kwargs={'args': args})

    exec_ = exec
