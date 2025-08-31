#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>


from calibre.customize import AIProviderPlugin


class OpenRouterAI(AIProviderPlugin):
    name = 'OpenRouter'
    version        = (1, 0, 0)
    description    = _('AI services from OpenRouter.ai. Allows choosing from hundreds of different AI models to query.')
    author = 'Kovid Goyal'
    builtin_live_module_name = 'calibre.ai.open_router.backend'

    @property
    def capabilities(self):
        from calibre.ai import AICapabilities
        return AICapabilities.text_to_text | AICapabilities.text_to_image
