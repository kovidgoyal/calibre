#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from functools import partial
from zipfile import ZipFile

from PyQt4.Qt import QToolButton, QAction, QIcon, QObject

from calibre.gui2 import Dispatcher

class InterfaceAction(QObject):

    '''
    A plugin representing an "action" that can be taken in the graphical user
    interface. All the items in the toolbar and context menus are implemented
    by these plugins.

    Note that this class is the base class for these plugins, however, to
    integrate the plugin with calibre's plugin system, you have to make a
    wrapper class that references the actual plugin. See the
    :mod:`calibre.customize.builtins` module for examples.

    If two :class:`InterfaceAction` objects have the same name, the one with higher
    priority takes precedence.

    Sub-classes should implement the :meth:`genesis`, :meth:`library_moved`,
    :meth:`location_selected` :meth:`shutting_down`
    and :meth:`initialization_complete` methods.

    Once initialized, this plugin has access to the main calibre GUI via the
    :attr:`gui` member. You can access other plugins by name, for example::

        self.gui.iactions['Save To Disk']

    To access the actual plugin, use the :attr:`interface_action_base_plugin`
    attribute, this attribute only becomes available after the plugin has been
    initialized. Useful if you want to use methods from the plugin class like
    do_user_config().

    The QAction specified by :attr:`action_spec` is automatically create and
    made available as ``self.qaction``.

    '''

    #: The plugin name. If two plugins with the same name are present, the one
    #: with higher priority takes precedence.
    name = 'Implement me'

    #: The plugin priority. If two plugins with the same name are present, the one
    #: with higher priority takes precedence.
    priority = 1

    #: The menu popup type for when this plugin is added to a toolbar
    popup_type = QToolButton.MenuButtonPopup

    #: Whether this action should be auto repeated when its shortcut
    #: key is held down.
    auto_repeat = False

    #: Of the form: (text, icon_path, tooltip, keyboard shortcut)
    #: icon, tooltip and keyboard shortcut can be None
    #: shortcut must be a translated string if not None
    action_spec = ('text', 'icon', None, None)

    #: Set of locations to which this action must not be added.
    #: See :attr:`all_locations` for a list of possible locations
    dont_add_to = frozenset([])

    #: Set of locations from which this action must not be removed.
    #: See :attr:`all_locations` for a list of possible locations
    dont_remove_from = frozenset([])

    all_locations = frozenset(['toolbar', 'toolbar-device', 'context-menu',
        'context-menu-device'])

    #: Type of action
    #: 'current' means acts on the current view
    #: 'global' means an action that does not act on the current view, but rather
    #: on calibre as a whole
    action_type = 'global'

    def __init__(self, parent, site_customization):
        QObject.__init__(self, parent)
        self.setObjectName(self.name)
        self.gui = parent
        self.site_customization = site_customization
        self.interface_action_base_plugin = None

    def do_genesis(self):
        self.Dispatcher = partial(Dispatcher, parent=self)
        self.create_action()
        self.gui.addAction(self.qaction)
        self.genesis()

    def create_action(self, spec=None, attr='qaction'):
        if spec is None:
            spec = self.action_spec
        text, icon, tooltip, shortcut = spec
        if icon is not None:
            action = QAction(QIcon(I(icon)), text, self.gui)
        else:
            action = QAction(text, self.gui)
        action.setAutoRepeat(self.auto_repeat)
        text = tooltip if tooltip else text
        action.setToolTip(text)
        action.setStatusTip(text)
        action.setWhatsThis(text)
        action.setAutoRepeat(False)
        if shortcut:
            action.setShortcut(shortcut)
        setattr(self, attr, action)
        return action

    def load_resources(self, names):
        '''
        If this plugin comes in a ZIP file (user added plugin), this method
        will allow you to load resources from the ZIP file.

        For example to load an image::

            pixmap = QPixmap()
            pixmap.loadFromData(self.load_resources(['images/icon.png']).itervalues().next())
            icon = QIcon(pixmap)

        :param names: List of paths to resources in the zip file using / as separator

        :return: A dictionary of the form ``{name : file_contents}``. Any names
                 that were not found in the zip file will not be present in the
                 dictionary.

        '''
        if self.plugin_path is None:
            raise ValueError('This plugin was not loaded from a ZIP file')
        ans = {}
        with ZipFile(self.plugin_path, 'r') as zf:
            for candidate in zf.namelist():
                if candidate in names:
                    ans[candidate] = zf.read(candidate)
        return ans


    def genesis(self):
        '''
        Setup this plugin. Only called once during initialization. self.gui is
        available. The action secified by :attr:`action_spec` is available as
        ``self.qaction``.
        '''
        pass

    def location_selected(self, loc):
        '''
        Called whenever the book list being displayed in calibre changes.
        Currently values for loc are: ``library, main, card and cardb``.

        This method should enable/disable this action and its sub actions as
        appropriate for the location.
        '''
        pass

    def library_changed(self, db):
        '''
        Called whenever the current library is changed.

        :param db: The LibraryDatabase corresponding to the current library.

        '''
        pass

    def initialization_complete(self):
        '''
        Called once per action when the initialization of the main GUI is
        completed.
        '''
        pass

    def shutting_down(self):
        '''
        Called once per plugin when the main GUI is in the process of shutting
        down. Release any used resources, but try not to block the shutdown for
        long periods of time.

        :return: False to halt the shutdown. You are responsible for telling
                 the user why the shutdown was halted.

        '''
        return True
