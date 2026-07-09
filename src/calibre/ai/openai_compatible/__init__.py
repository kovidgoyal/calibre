#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, OpenAI

from calibre.customize import AIProviderPlugin


class OpenAICompatible(AIProviderPlugin):
    name = 'OpenAI compatible'
    version = (1, 0, 0)
    description = _(
        'Generic OpenAI compatible AI services. Use this to connect calibre to self-hosted or third-party services'
        ' that implement the OpenAI chat completions API.'
    )
    author = 'OpenAI'
    builtin_live_module_name = 'calibre.ai.openai_compatible.backend'

    @property
    def capabilities(self):
        from calibre.ai import AICapabilities
        return AICapabilities.text_to_text
