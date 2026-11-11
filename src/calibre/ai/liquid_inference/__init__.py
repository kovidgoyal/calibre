#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Loc Nguyen

from typing import TYPE_CHECKING

from calibre.customize import AIProviderPlugin
from calibre.utils.localization import _

if TYPE_CHECKING:
    from calibre.ai import AICapabilities
else:
    AICapabilities = object


class LiquidInference(AIProviderPlugin):
    name = 'Liquid Inference'
    version = (1, 0, 0)
    description = _('Ask about books and selected text with models from Liquid Inference.')
    author = 'Loc Nguyen'
    builtin_live_module_name = 'calibre.ai.liquid_inference.backend'

    @property
    def capabilities(self) -> AICapabilities:
        from calibre.ai import AICapabilities

        return AICapabilities.text_to_text
