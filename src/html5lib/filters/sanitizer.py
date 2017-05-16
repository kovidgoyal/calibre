from __future__ import absolute_import, division, unicode_literals

from . import base
from ..sanitizer import HTMLSanitizerMixin


class Filter(base.Filter, HTMLSanitizerMixin):
    def __iter__(self):
        for token in base.Filter.__iter__(self):
            token = self.sanitize_token(token)
            if token:
                yield token
