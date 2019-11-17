#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2019, Eli Schwartz <eschwartz@archlinux.org>

from polyglot.builtins import is_py3

if is_py3:
    from reprlib import repr
else:
    from repr import repr
