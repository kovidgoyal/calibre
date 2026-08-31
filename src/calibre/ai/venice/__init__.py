#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

from typing import TYPE_CHECKING

from calibre.customize import AIProviderPlugin
from calibre.utils.localization import _

if TYPE_CHECKING:
    from calibre.ai import AICapabilities
else:
    AICapabilities = object


class VeniceAI(AIProviderPlugin):
    name = 'Venice AI'
    version = (1, 0, 0)
    description = _('Venice AI: privacy focused, uncensored AI service')
    author = 'Kovid Goyal'
    builtin_live_module_name = 'calibre.ai.venice.backend'

    @property
    def capabilities(self) -> AICapabilities:
        from calibre.ai import AICapabilities

        return AICapabilities.text_to_text | AICapabilities.text_to_image
