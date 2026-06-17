#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Ali Sheikhizadeh (Al00X) <al00x@outlook.com> <https://al00x.com>
# Based on code Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

from calibre.customize import AIProviderPlugin


class LMStudioAI(AIProviderPlugin):
    DEFAULT_URL = 'http://localhost:1234'
    name = 'LMStudio'
    version        = (1, 0, 0)
    description    = _('AI services from LM Studio, when you want to run AI models yourself rather than rely on a third party provider.')
    author = 'Al00X'
    builtin_live_module_name = 'calibre.ai.lm_studio.backend'

    @property
    def capabilities(self):
        from calibre.ai import AICapabilities
        return AICapabilities.text_to_text
