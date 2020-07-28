#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import importlib

from PyQt5.Qt import QToolButton

from calibre import prints
from calibre.customize.ui import all_edit_book_tool_plugins
from calibre.gui2.tweak_book import tprefs, current_container
from calibre.gui2.tweak_book.boss import get_boss
from polyglot.builtins import itervalues, unicode_type


class Tool(object):

    '''
    The base class for individual tools in an Edit Book plugin. Useful members include:

        * ``self.plugin``: A reference to the :class:`calibre.customize.Plugin` object to which this tool belongs.
        * self. :attr:`boss`
        * self. :attr:`gui`

    Methods that must be overridden in sub classes:

        * :meth:`create_action`
        * :meth:`register_shortcut`

    '''

    #: Set this to a unique name it will be used as a key
    name = None

    #: If True the user can choose to place this tool in the plugins toolbar
    allowed_in_toolbar = True

    #: If True the user can choose to place this tool in the plugins menu
    allowed_in_menu = True

    #: The popup mode for the menu (if any) of the toolbar button. Possible values are 'delayed', 'instant', 'button'
    toolbar_button_popup_mode = 'delayed'

    @property
    def boss(self):
        ' The :class:`calibre.gui2.tweak_book.boss.Boss` object. Used to control the user interface. '
        return get_boss()

    @property
    def gui(self):
        ' The main window of the user interface '
        return self.boss.gui

    @property
    def current_container(self):
        ' Return the current :class:`calibre.ebooks.oeb.polish.container.Container` object that represents the book being edited. '
        return current_container()

    def register_shortcut(self, qaction, unique_name, default_keys=(), short_text=None, description=None, **extra_data):
        '''
        Register a keyboard shortcut that will trigger the specified ``qaction``. This keyboard shortcut
        will become automatically customizable by the user in the Keyboard section of the editor preferences.

        :param qaction: A QAction object, it will be triggered when the
            configured key combination is pressed by the user.
        :param unique_name: A unique name for this shortcut/action. It will be
            used internally, it must not be shared by any other actions in this
            plugin.
        :param default_keys: A list of the default keyboard shortcuts. If not
            specified no default shortcuts will be set. If the shortcuts specified
            here conflict with either builtin shortcuts or shortcuts from user
            configuration/other plugins, they will be ignored. In that case, users
            will have to configure the shortcuts manually via Preferences. For example:
            ``default_keys=('Ctrl+J', 'F9')``.
        :param short_text: An optional short description of this action. If not
            specified the text from the QAction will be used.
        :param description: An optional longer description of this action, it
            will be used in the preferences entry for this shortcut.
        '''
        short_text = short_text or unicode_type(qaction.text()).replace('&&', '\0').replace('&', '').replace('\0', '&')
        self.gui.keyboard.register_shortcut(
            self.name + '_' + unique_name, short_text, default_keys=default_keys, action=qaction,
            description=description or '', group=_('Plugins'))

    def create_action(self, for_toolbar=True):
        '''
        Create a QAction that will be added to either the plugins toolbar or
        the plugins menu depending on ``for_toolbar``. For example::

            def create_action(self, for_toolbar=True):
                ac = QAction(get_icons('myicon.png'), 'Do something')
                if for_toolbar:
                    # We want the toolbar button to have a popup menu
                    menu = QMenu()
                    ac.setMenu(menu)
                    menu.addAction('Do something else')
                    subaction = menu.addAction('And another')

                    # Register a keyboard shortcut for this toolbar action be
                    # careful to do this for only one of the toolbar action or
                    # the menu action, not both.
                    self.register_shortcut(ac, 'some-unique-name', default_keys=('Ctrl+K',))
                return ac

        .. seealso:: Method :meth:`register_shortcut`.
        '''
        raise NotImplementedError()


def load_plugin_tools(plugin):
    try:
        main = importlib.import_module(plugin.__class__.__module__+'.main')
    except ImportError:
        import traceback
        traceback.print_exc()
    else:
        for x in itervalues(vars(main)):
            if isinstance(x, type) and x is not Tool and issubclass(x, Tool):
                ans = x()
                ans.plugin = plugin
                yield ans


def plugin_action_sid(plugin, tool, for_toolbar=True):
    return plugin.name + tool.name + ('toolbar' if for_toolbar else 'menu')


plugin_toolbar_actions = []


def create_plugin_action(plugin, tool, for_toolbar, actions=None, toolbar_actions=None, plugin_menu_actions=None):
    try:
        ac = tool.create_action(for_toolbar=for_toolbar)
        if ac is None:
            raise RuntimeError('create_action() failed to return an action')
    except Exception:
        prints('Failed to create action for tool:', tool.name)
        import traceback
        traceback.print_exc()
        return
    sid = plugin_action_sid(plugin, tool, for_toolbar)
    if actions is not None and sid in actions:
        prints('The %s tool from the %s plugin has a non unique name, ignoring' % (tool.name, plugin.name))
    else:
        if actions is not None:
            actions[sid] = ac
        ac.sid = sid
        if for_toolbar:
            if toolbar_actions is not None:
                toolbar_actions[sid] = ac
                plugin_toolbar_actions.append(ac)
            ac.popup_mode = {'instant':QToolButton.InstantPopup, 'button':QToolButton.MenuButtonPopup}.get(
                tool.toolbar_button_popup_mode, QToolButton.DelayedPopup)
        else:
            if plugin_menu_actions is not None:
                plugin_menu_actions.append(ac)
    return ac


_tool_memory = []  # Needed to prevent the tool object from being garbage collected


def create_plugin_actions(actions, toolbar_actions, plugin_menu_actions):
    del _tool_memory[:]
    del plugin_toolbar_actions[:]

    for plugin in all_edit_book_tool_plugins():
        for tool in load_plugin_tools(plugin):
            _tool_memory.append(tool)
            if tool.allowed_in_toolbar:
                create_plugin_action(plugin, tool, True, actions, toolbar_actions, plugin_menu_actions)
            if tool.allowed_in_menu:
                create_plugin_action(plugin, tool, False, actions, toolbar_actions, plugin_menu_actions)


def install_plugin(plugin):
    for tool in load_plugin_tools(plugin):
        if tool.allowed_in_toolbar:
            sid = plugin_action_sid(plugin, tool, True)
            if sid not in tprefs['global_plugins_toolbar']:
                tprefs['global_plugins_toolbar'] = tprefs['global_plugins_toolbar'] + [sid]
