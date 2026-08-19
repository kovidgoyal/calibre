#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

from typing import TYPE_CHECKING

from calibre.customize import AIProviderPlugin
from calibre.utils.localization import _

if TYPE_CHECKING:
    from calibre.ai import AICapabilities
else:
    AICapabilities = object


class AnthropicAI(AIProviderPlugin):
    name = 'Anthropic'
    version = (1, 0, 0)
    description = _('AI services from Anthropic, the makers of the Claude family of AI models.')
    author = 'Kovid Goyal'
    builtin_live_module_name = 'calibre.ai.anthropic.backend'

    @property
    def capabilities(self) -> AICapabilities:
        from calibre.ai import AICapabilities

        return AICapabilities.text_to_text
