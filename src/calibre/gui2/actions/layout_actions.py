#!/usr/bin/env python
# License: GPLv3 Copyright: 2022, Charles Haley

from enum import Enum
from functools import partial

from qt.core import QComboBox, QDialog, QDialogButtonBox, QFormLayout, QIcon, QLabel, QMenu, QToolButton, QVBoxLayout

from calibre.gui2 import error_dialog, gprefs, question_dialog
from calibre.gui2.actions import InterfaceAction, show_menu_under_widget
from calibre.gui2.geometry import _restore_geometry, delete_geometry, save_geometry
from calibre.utils.icu import sort_key


class Panel(Enum):
    ' See gui2.init for these '
    SEARCH_BAR = 'sb'
    TAG_BROWSER = 'tb'
    BOOK_DETAILS = 'bd'
    GRID_VIEW = 'gv'
    COVER_BROWSER = 'cb'
    QUICKVIEW = 'qv'


class SaveLayoutDialog(QDialog):

    def __init__(self, parent, names):
        QDialog.__init__(self, parent)
        self.names = names
        l = QVBoxLayout(self)
        fl = QFormLayout()
        l.addLayout(fl)
        self.cb = cb = QComboBox()
        cb.setEditable(True)
        cb.setMinimumWidth(200)
        cb.addItem('')
        cb.addItems(sorted(names, key=sort_key))
        fl.addRow(QLabel(_('Layout name')), cb)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        l.addWidget(bb)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)

    def current_name(self):
        return self.cb.currentText().strip()

    def accept(self):
        n = self.current_name()
        if not n:
            error_dialog(self, _('Invalid name'), _('The settings name cannot be blank'),
                         show=True, show_copy_button=False)
            return
        if self.current_name() in self.names:
            r = question_dialog(self, _('Replace saved layout'),
                  _('Do you really want to overwrite the saved layout {0}?').format(self.current_name()))
            if r == QDialog.DialogCode.Accepted:
                super().accept()
            else:
                return
        super().accept()


class LayoutActions(InterfaceAction):

    name = 'Layout Actions'
    action_spec = (_('Layout actions'), 'layout.png',
                   _("Save and restore layout item sizes, and add/remove/toggle "
                     "layout items such as the search bar, tag browser, etc. "
                     "Item sizes in saved layouts are saved as a percentage of "
                     "the window size. Restoring a layout doesn't change the "
                     "window size, instead fitting the items into the current window."), None)

    action_type = 'current'
    popup_type = QToolButton.ToolButtonPopupMode.InstantPopup
    action_add_menu = True
    dont_add_to = frozenset({'context-menu-device', 'menubar-device'})

    def genesis(self):
        self.layout_icon = QIcon.ic('layout.png')
        self.menu = m = self.qaction.menu()
        m.aboutToShow.connect(self.about_to_show_menu)

        # Create a "hidden" menu that can have a shortcut.
        self.hidden_menu = QMenu()
        self.shortcut_action = self.create_menu_action(
                        menu=self.hidden_menu,
                        unique_name='Main window layout',
                        shortcut=None,
                        text=_("Save and restore layout item sizes, and add/remove/toggle "
                               "layout items such as the search bar, tag browser, etc. "),
                        icon='layout.png',
                        triggered=self.show_menu)

    # We want to show the menu when a shortcut is used. Apparently the only way
    # to do that is to scan the toolbar(s) for the action button then exec the
    # associated menu. The search is done here to take adding and removing the
    # action from toolbars into account.
    #
    # If a shortcut is triggered and there isn't a toolbar button visible then
    # show the menu in the upper left corner of the library view pane. Yes, this
    # is a bit weird but it works as well as a popping up a dialog.
    def show_menu(self):
        show_menu_under_widget(self.gui, self.menu, self.qaction, self.name)

    def toggle_layout(self):
        self.gui.layout_container.toggle_layout()

    def gui_layout_complete(self):
        m = self.qaction.menu()
        m.aboutToShow.connect(self.about_to_show_menu)

    def initialization_complete(self):
        self.populate_menu()

    def about_to_show_menu(self):
        self.populate_menu()

    def populate_menu(self):
        m = self.qaction.menu()
        m.clear()
        lm = m.addMenu(self.layout_icon, _('Restore saved layout'))
        layouts = gprefs['saved_layouts']
        if layouts:
            for l in sorted(layouts, key=sort_key):
                lm.addAction(self.layout_icon, l, partial(self.apply_layout, l))
        else:
            lm.setEnabled(False)
        lm = m.addAction(self.layout_icon, _('Save current layout'))
        lm.triggered.connect(self.save_current_layout)
        lm = m.addMenu(self.layout_icon, _('Delete saved layout'))
        layouts = gprefs['saved_layouts']
        if layouts:
            for l in sorted(layouts, key=sort_key):
                lm.addAction(self.layout_icon, l, partial(self.delete_layout, l))
        else:
            lm.setEnabled(False)

        m.addSeparator()
        m.addAction(_('Hide all'), self.hide_all)
        for button, name in zip(self.gui.layout_buttons, self.gui.button_order):
            m.addSeparator()
            ic = button.icon()
            m.addAction(ic, _('Show {}').format(button.label), partial(self.set_visible, Panel(name), True))
            m.addAction(ic, _('Hide {}').format(button.label), partial(self.set_visible, Panel(name), False))
            m.addAction(ic, _('Toggle {}').format(button.label), partial(self.toggle_item, Panel(name)))

    def _change_item(self, button, show=True):
        if button.isChecked() and not show:
            button.click()
        elif not button.isChecked() and show:
            button.click()

    def _toggle_item(self, button):
        button.click()

    def _button_from_enum(self, name: Panel):
        for q, b in zip(self.gui.button_order, self.gui.layout_buttons):
            if q == name.value:
                return b

    # Public API
    def apply_layout(self, name):
        '''apply_layout()
        Apply a saved GUI panel layout.

        :param:`name` The name of the saved layout

         Throws KeyError if the name doesn't exist.
        '''
        # This can be called by plugins so let the exception fly

        # Restore the application window geometry if we have it.
        _restore_geometry(self.gui, gprefs, f'saved_layout_{name}')
        # Now the panel sizes inside the central widget
        layouts = gprefs['saved_layouts']
        settings = layouts[name]
        # Order is important here. change_layout() must be called before
        # unserializing the settings or panes like book details won't display
        # properly.
        self.gui.layout_container.change_layout(self.gui, settings['layout'] == 'wide')
        self.gui.layout_container.unserialize_settings(settings)
        self.gui.layout_container.relayout()

    def save_current_layout(self):
        '''save_current_layout()
        Opens a dialog asking for the name to use to save the current layout.
        Saves the current settings under the provided name.
        '''
        layouts = gprefs['saved_layouts']
        d = SaveLayoutDialog(self.gui, layouts.keys())
        if d.exec() == QDialog.DialogCode.Accepted:
            self.save_named_layout(d.current_name(), self.current_settings())

    def current_settings(self):
        '''current_settings()

        :return: the current gui layout settings.
        '''

        return self.gui.layout_container.serialized_settings()

    def save_named_layout(self, name, settings):
        '''save_named_layout()
        Saves the settings under the provided name.

        :param:`name` The name for the settings.
        :param:`settings`: The gui layout settings to save.
        '''
        # Save the main window geometry.
        save_geometry(self.gui, gprefs, f'saved_layout_{name}')
        # Now the panel sizes inside the central widget
        layouts = gprefs['saved_layouts']
        layouts.update({name: settings})
        gprefs['saved_layouts'] = layouts
        self.populate_menu()

    def delete_layout(self, name, show_warning=True):
        '''delete_layout()
        Delete a saved layout.

        :param:`name` The name of the layout to delete
        :param:`show_warning`: If True a warning dialog will be shown before deleting the layout.
        '''
        if show_warning:
            if not question_dialog(self.gui, _('Are you sure?'),
                                   _('Do you really want to delete the saved layout {0}?').format(name),
                                   skip_dialog_name='delete_saved_gui_layout'):
                return

        # The information is stored as 2 preferences. Delete them both.
        delete_geometry(gprefs, f'saved_layout_{name}')
        layouts = gprefs['saved_layouts']
        layouts.pop(name, None)
        self.populate_menu()

    def saved_layout_names(self):
        '''saved_layout_names()
        Get a list of saved layout names

        :return: the sorted list of names. The list is empty if there are no names.
        '''
        layouts = gprefs['saved_layouts']
        return sorted(layouts.keys(), key=sort_key)

    def toggle_item(self, name):
        '''toggle_item()
        Toggle the visibility of the panel.

        :param name: specifies which panel to toggle. Valid names are
            SEARCH_BAR: 'sb'
            TAG_BROWSER: 'tb'
            BOOK_DETAILS: 'bd'
            GRID_VIEW: 'gv'
            COVER_BROWSER: 'cb'
            QUICKVIEW: 'qv'
        '''
        self._toggle_item(self._button_from_enum(name))

    def set_visible(self, name: Panel, show=True):
        '''set_visible()
        Show or hide a panel. Does nothing if the panel is already in the
        desired state.

        :param name: specifies which panel to show.  Valid names are
            SEARCH_BAR: 'sb'
            TAG_BROWSER: 'tb'
            BOOK_DETAILS: 'bd'
            GRID_VIEW: 'gv'
            COVER_BROWSER: 'cb'
            QUICKVIEW: 'qv'
        :param show: If True, show the panel, otherwise hide the panel
        '''
        self._change_item(self._button_from_enum(name), show)

    def is_visible(self, name: Panel):
        '''is_visible()
        Returns True if the panel is visible.

        :param name: specifies which panel. Valid names are
            SEARCH_BAR: 'sb'
            TAG_BROWSER: 'tb'
            BOOK_DETAILS: 'bd'
            GRID_VIEW: 'gv'
            COVER_BROWSER: 'cb'
            QUICKVIEW: 'qv'
        '''
        self._button_from_enum(name).isChecked()

    def hide_all(self):
        for name in self.gui.button_order:
            self.set_visible(Panel(name), show=False)

    def show_all(self):
        for name in self.gui.button_order:
            self.set_visible(Panel(name), show=True)

    def panel_titles(self):
        '''panel_titles()
        Return a dictionary of Panel Enum items to translated human readable title.
        Simplifies building dialogs, for example combo boxes of all the panel
        names or check boxes for each panel.

        :return: {Panel_enum_value: human readable title, ...}
        '''
        return {p: self._button_from_enum(p).label for p in Panel}
