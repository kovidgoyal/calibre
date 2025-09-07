#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

from calibre.customize import AIProviderPlugin


class GoogleAI(AIProviderPlugin):
    name = 'GoogleAI'
    version        = (1, 0, 0)
    description    = _('AI services from Google')
    author = 'Kovid Goyal'
    builtin_live_module_name = 'calibre.ai.google.backend'

    @property
    def capabilities(self):
        from calibre.ai import AICapabilities
        return AICapabilities.text_to_text | AICapabilities.text_to_image
