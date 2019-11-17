#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2019, Eli Schwartz <eschwartz@archlinux.org>

from polyglot.builtins import is_py3

if is_py3:
    from queue import Queue, Empty, Full, PriorityQueue, LifoQueue  # noqa
else:
    from Queue import Queue, Empty, Full, PriorityQueue, LifoQueue  # noqa
