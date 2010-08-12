#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from calibre.customize import InterfaceActionBase

class InterfaceAction(InterfaceActionBase):

    supported_platforms = ['windows', 'osx', 'linux']
    author         = 'Kovid Goyal'
    type = _('User Interface Action')

    positions = frozenset([])
    separators = frozenset([])

    def do_genesis(self, gui):
        self.gui = gui
        self.genesis()

    # Subclassable methods {{{
    def genesis(self):
        raise NotImplementedError()
    # }}}

