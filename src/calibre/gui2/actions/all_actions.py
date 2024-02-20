#!/usr/bin/env python
# License: GPLv3 Copyright: 2022, Charles Haley

from functools import partial
from math import ceil

from qt.core import QIcon, QMenu, QToolButton, Qt

from calibre.gui2.actions import InterfaceAction, show_menu_under_widget
from calibre.gui2.preferences.toolbar import AllModel, CurrentModel
from calibre.utils.icu import sort_key


class AllGUIActions(InterfaceAction):

    name = 'All GUI actions'
    action_spec = (_('All GUI actions'), 'wizard.png',
                   _("Show a menu of all available GUI and plugin actions.\nThis menu "
                     "is not available when looking at books on a device"), None)

    action_type = 'current'
    popup_type = QToolButton.ToolButtonPopupMode.InstantPopup
    action_add_menu = True
    dont_add_to = frozenset()

    def genesis(self):
        self.layout_icon = QIcon.ic('wizard.png')
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

    def gui_layout_complete(self):
        self.qaction.menu().aboutToShow.connect(self.about_to_show_menu)

    def initialization_complete(self):
        self.populate_menu()

    def about_to_show_menu(self):
        self.populate_menu()

    def location_selected(self, loc):
        self.qaction.setEnabled(loc == 'library')

    def populate_menu(self):
        # Need to do this on every invocation because shortcuts can change
        m = self.qaction.menu()
        m.clear()

        name_data = {} # A dict of display names to actions data

        # Use model data from Preferences / Toolbars, with location 'toolbar' or
        # 'toolbar-device' depending on whether a device is connected.
        location = 'toolbar' + ('-device' if self.gui.location_manager.has_device else '')
        for model in (AllModel(location, self.gui), CurrentModel(location, self.gui)):
            for i in range(0, model.rowCount(None)):
                dex = model.index(i)
                name = model.names((dex,))[0] # this is the action name
                if name is not None and not name.startswith('---'):
                    name_data[model.data(dex, Qt.ItemDataRole.DisplayRole)] = {
                                    'action': model.name_to_action(name, self.gui),
                                    'action_name':name,
                                    'icon': model.data(dex, Qt.ItemDataRole.DecorationRole)}
        # The loop leaves the variable 'model' set to a valid value

        # Get display names of builtin and user plugins. We tell the difference
        # using the class full module name. Plugins start with 'calibre_plugins'
        builtin_actions = list()
        user_plugins = list()
        for display_name, act_data in name_data.items():
            act = model.name_to_action(act_data['action_name'], self.gui)
            if act is not None:
                module = f'{act.__module__}.{act.__class__ .__name__}'
                if module.startswith('calibre_plugins'):
                    user_plugins.append(display_name)
                else:
                    builtin_actions.append(display_name)

        builtin_actions = sorted(builtin_actions, key=sort_key)
        user_plugins = sorted(user_plugins, key=sort_key)

        # Build the map of action shortcuts so we can display the shortcuts for
        # the actions. For shortcuts sometimes the action name and sometimes the
        # display name is used. Test both. Unfortunately, there are case
        # differences to deal with so we use lower case keys.
        lower_names = ({n['action_name'].lower() for n in name_data.values()} |
                       {n.lower() for n in name_data.keys()})
        kbd = self.gui.keyboard
        shortcut_map = {}
        for n,v in kbd.keys_map.items():
            act_name = kbd.shortcuts[n]['name'].lower()
            if act_name in lower_names:
                shortcuts = list((sc.toString() for sc in v))
                shortcut_map[act_name] = f'\t{", ".join(shortcuts)}'

        # This function constructs a menu action, dealing with the action being
        # either a popup menu or a dialog. It adds the shortcuts to the menu
        # line. Happily, a tab causes the shortcuts to be right-aligned. The tab
        # is added when the shortcut map is built.
        def add_action(menu, display_name):
            shortcuts = shortcut_map.get(display_name.lower(), '')
            act = name_data[display_name]['action']
            if not hasattr(act, 'popup_type'): # FakeAction
                return
            menu_text = f'{display_name}{shortcuts}'
            icon = name_data[display_name]['icon']
            if act.popup_type == QToolButton.ToolButtonPopupMode.MenuButtonPopup:
                if getattr(act, 'action_add_menu', None) or (getattr(act, 'qaction', None) and act.qaction.menu() and act.qaction.menu().children()):
                    # The action offers both a 'click' and a menu. Use the menu.
                    menu.addAction(icon, menu_text, partial(self._do_menu, display_name, act))
                else:
                    # The action is a dialog.
                    menu.addAction(act.qaction.icon(), menu_text, partial(self._do_action, act))
            else:
                # The action is a menu.
                menu.addAction(icon, menu_text, partial(self._do_menu, display_name, act))

        # Finally the real work, building the action menu. Partition long lists
        # of actions into sublists of some arbitrary length.
        def partition(names):
            count_in_partition = 10 # arbitrary
            if len(names) >= count_in_partition:
                partition_count = len(names) // (count_in_partition - 1)
                step = int(ceil(len(names) / partition_count))
                for first in range(0, len(names), step):
                    last = min(first + step - 1, len(names) - 1)
                    dnf = names[first]
                    dnl = names[last]
                    if dnf != dnl:
                        sm = m.addMenu(QIcon.ic('wizard.png'), f'{dnf} - {dnl}')
                    else:
                        sm = m.addMenu(QIcon.ic('wizard.png'), f'{dnf}')
                    for name in names[first:last+1]:
                        add_action(sm, name)
            else:
                for name in names:
                    add_action(m, name)

        # Add a named section for builtin actions if user plugins are installed.
        if user_plugins:
            m.addSection(_('Built-in calibre actions') + ' ')
            partition(builtin_actions)
            m.addSection(_('Plugins') + ' ')
            partition(user_plugins)
        else:
            partition(builtin_actions)
        # Add access to the toolbars and keyboard shortcuts preferences dialogs
        m.addSection(_('Preferences') + ' ')
        m.addAction(QIcon.ic('wizard.png'), _('Toolbars'), self._do_pref_toolbar)
        m.addAction(QIcon.ic('keyboard-prefs.png'), _('Keyboard shortcuts'), self._do_pref_shortcuts)

    def _do_pref_toolbar(self):
        self.gui.iactions['Preferences'].do_config(initial_plugin=('Interface', 'Toolbar'), close_after_initial=True)

    def _do_pref_shortcuts(self):
        self.gui.iactions['Preferences'].do_config(initial_plugin=('Advanced', 'Keyboard'), close_after_initial=True)

    def _do_action(self, action):
        action.qaction.trigger()

    def _do_menu(self, name, action):
        # This method clones and shows the action's menu. If the action is in a
        # context menu, the action menu is displayed there without using this
        # method. If not it is displayed underneath a toolbar or menu button. If
        # neither is true then the menu is displayed in the upper left corner.
        menu = QMenu()
        menu.addSection(name)
        action.qaction.menu().aboutToShow.emit()
        for m in action.qaction.menu().actions():
            menu.addAction(m)
        show_menu_under_widget(self.gui, menu, self.qaction, self.name)
