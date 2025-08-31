#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

from enum import Flag, auto


class AICapabilities(Flag):
    none = auto()
    text_to_text = auto()
    text_to_image = auto()

    @property
    def supports_text_to_text(self) -> bool:
        return AICapabilities.text_to_text in self

    @property
    def supports_text_to_image(self) -> bool:
        return AICapabilities.text_to_image in self
