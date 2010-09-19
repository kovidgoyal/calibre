#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.gui2.actions import InterfaceAction

class TweakEpubAction(InterfaceAction):

    name = 'Tweak ePub'
    action_spec = (_('Edit ePub in situ'), 'document_open.png', None, None)
    dont_add_to = frozenset(['toolbar-device', 'context-menu-device'])
    action_type = 'current'

    def genesis(self):
        self.qaction.triggered.connect(self.edit_epub_in_situ)
        print "gui2.actions.tweak_epub:TweakEpubAction.genesis()"

    def initialization_complete(self):
        print "gui2.actions.tweak_epub:TweakEpubAction.initialization_complete()"

    def library_changed(self, db):
        print "gui2.actions.tweak_epub:TweakEpubAction.library_changed()"

    def location_selected(self, loc):
        print "gui2.actions.tweak_epub:TweakEpubAction.location_selected()"

    def shutting_down(self):
        print "gui2.actions.tweak_epub:TweakEpubAction.shutting_down()"

    def edit_epub_in_situ(self, *args):
        print "gui2.actions.tweak_epub:TweakEpubAction.edit_epub_in_situ()"
