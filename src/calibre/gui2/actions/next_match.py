#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.gui2.actions import InterfaceAction


class NextMatchAction(InterfaceAction):
    name = 'Move to next highlighted book'
    action_spec = (_('Move to next match'), 'arrow-down.png',
            _('Move to next highlighted match'), [_('N'), _('F3')])
    dont_add_to = frozenset(('context-menu-device',))
    action_type = 'current'

    def genesis(self):
        '''
        Setup this plugin. Only called once during initialization. self.gui is
        available. The action secified by :attr:`action_spec` is available as
        ``self.qaction``.
        '''
        self.can_move = None
        self.qaction.triggered.connect(self.move_forward)
        self.create_action(spec=(_('Move to previous item'), 'arrow-up.png',
              _('Move to previous highlighted item'), ['Shift+N',
                  'Shift+F3']), attr='p_action')
        self.gui.addAction(self.p_action)
        self.p_action.triggered.connect(self.move_backward)

    def location_selected(self, loc):
        self.can_move = loc == 'library'

    def move_forward(self):
        if self.can_move is None:
            self.can_move = self.gui.current_view() is self.gui.library_view

        if self.can_move:
            self.gui.current_view().move_highlighted_row(forward=True)

    def move_backward(self):
        if self.can_move is None:
            self.can_move = self.gui.current_view() is self.gui.library_view

        if self.can_move:
            self.gui.current_view().move_highlighted_row(forward=False)
