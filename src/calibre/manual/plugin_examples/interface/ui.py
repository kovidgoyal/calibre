#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


# The class that all interface action plugins must inherit from
from calibre.gui2.actions import InterfaceAction

if False:
    # This is here to keep my python error checker from complaining about
    # the builtins that will be defined by the plugin loading system
    get_icons = None

class InterfacePlugin(InterfaceAction):

    name = 'Interface Plugin Demo'

    action_spec = ('Interface Plugin Demo', None,
            'Run the Interface Plugin Demo', 'Ctrl+Shift+F1')

    def genesis(self):
        # This method is called once per plugin, do initial setup here
        print (1111, get_icons('icon.png'))
        self.qaction.setIcon(get_icons('icon.png'))

