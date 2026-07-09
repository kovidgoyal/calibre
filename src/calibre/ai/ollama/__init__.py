#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

from calibre.customize import AIProviderPlugin


class OllamaAI(AIProviderPlugin):
    DEFAULT_URL = 'http://localhost:11434'
    name = 'OllamaAI'
    version        = (1, 0, 0)
    description    = _('AI services from Ollama, when you want to run AI models yourself rather than rely on a third party provider.')
    author = 'Kovid Goyal'
    builtin_live_module_name = 'calibre.ai.ollama.backend'

    @property
    def capabilities(self):
        from calibre.ai import AICapabilities
        return (
            AICapabilities.text_to_text
        )
