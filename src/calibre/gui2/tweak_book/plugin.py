#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

from calibre.gui2.tweak_book.boss import get_boss

class Tool(object):

    #: Set this to a unique name it will be used as a key
    name = None

    #: If True the user can choose to place this tool in the plugins toolbar
    allowed_in_toolbar = True

    #: If True the user can choose to place this tool in the plugins menu
    allowed_in_menu = True

    @property
    def boss(self):
        ' The :class:`calibre.gui2.tweak_book.boss.Boss` object. Used to control the user interface. '
        return get_boss()

    @property
    def gui(self):
        ' The main window of the user interface '
        return self.boss.gui

    def create_action(self, for_toolbar=True):
        '''
        Create a QAction that will be added to either the plugins toolbar or
        the plugins menu depending on ``for_toolbar``. For example::

            def create_action(self, for_toolbar):
                ac = QAction(
        '''
        raise NotImplementedError()

