#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from functools import partial
from zipfile import ZipFile

from PyQt4.Qt import (QToolButton, QAction, QIcon, QObject, QMenu,
        QKeySequence)

from calibre import prints
from calibre.gui2 import Dispatcher
from calibre.gui2.keyboard import NameConflict

def menu_action_unique_name(plugin, unique_name):
    return u'%s : menu action : %s'%(plugin.unique_name, unique_name)

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

    Sub-classes should implement the :meth:`genesis`, :meth:`library_changed`,
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
    #: shortcut must be a string, None or tuple of shortcuts.
    #: If None, a keyboard shortcut corresponding to the action is not
    #: registered. If you pass an empty tuple, then the shortcut is registered
    #: with no default key binding.
    action_spec = ('text', 'icon', None, None)

    #: If True, a menu is automatically created and added to self.qaction
    action_add_menu = False

    #: If True, a clone of self.qaction is added to the menu of self.qaction
    #: If you want the text of this action to be different from that of
    #: self.qaction, set this variable to the new text
    action_menu_clone_qaction = False

    #: Set of locations to which this action must not be added.
    #: See :attr:`all_locations` for a list of possible locations
    dont_add_to = frozenset([])

    #: Set of locations from which this action must not be removed.
    #: See :attr:`all_locations` for a list of possible locations
    dont_remove_from = frozenset([])

    all_locations = frozenset(['toolbar', 'toolbar-device', 'context-menu',
        'context-menu-device', 'toolbar-child', 'menubar', 'menubar-device',
        'context-menu-cover-browser'])

    #: Type of action
    #: 'current' means acts on the current view
    #: 'global' means an action that does not act on the current view, but rather
    #: on calibre as a whole
    action_type = 'global'

    #: If True, then this InterfaceAction will have the opportunity to interact
    #: with drag and drop events. See the methods, :meth:`accept_enter_event`,
    #: :meth`:accept_drag_move_event`, :meth:`drop_event` for details.
    accepts_drops = False

    def __init__(self, parent, site_customization):
        QObject.__init__(self, parent)
        self.setObjectName(self.name)
        self.gui = parent
        self.site_customization = site_customization
        self.interface_action_base_plugin = None

    def accept_enter_event(self, event, mime_data):
        ''' This method should return True iff this interface action is capable
        of handling the drag event. Do not call accept/ignore on the event,
        that will be taken care of by the calibre UI.'''
        return False

    def accept_drag_move_event(self, event, mime_data):
        ''' This method should return True iff this interface action is capable
        of handling the drag event. Do not call accept/ignore on the event,
        that will be taken care of by the calibre UI.'''
        return False

    def drop_event(self, event, mime_data):
        ''' This method should perform some useful action and return True
        iff this interface action is capable of handling the drag event. Do not
        call accept/ignore on the event, that will be taken care of by the
        calibre UI.'''
        return False

    def do_genesis(self):
        self.Dispatcher = partial(Dispatcher, parent=self)
        self.create_action()
        self.gui.addAction(self.qaction)
        self.gui.addAction(self.menuless_qaction)
        self.genesis()

    @property
    def unique_name(self):
        bn = self.__class__.__name__
        if getattr(self.interface_action_base_plugin, 'name'):
            bn = self.interface_action_base_plugin.name
        return u'Interface Action: %s (%s)'%(bn, self.name)

    def create_action(self, spec=None, attr='qaction', shortcut_name=None):
        if spec is None:
            spec = self.action_spec
        text, icon, tooltip, shortcut = spec
        if icon is not None:
            action = QAction(QIcon(I(icon)), text, self.gui)
        else:
            action = QAction(text, self.gui)
        if attr == 'qaction':
            mt = (action.text() if self.action_menu_clone_qaction is True else
                    unicode(self.action_menu_clone_qaction))
            self.menuless_qaction = ma = QAction(action.icon(), mt, self.gui)
            ma.triggered.connect(action.trigger)
        for a in ((action, ma) if attr == 'qaction' else (action,)):
            a.setAutoRepeat(self.auto_repeat)
            text = tooltip if tooltip else text
            a.setToolTip(text)
            a.setStatusTip(text)
            a.setWhatsThis(text)
        shortcut_action = action
        desc = tooltip if tooltip else None
        if attr == 'qaction':
            shortcut_action = ma
        if shortcut is not None:
            keys = ((shortcut,) if isinstance(shortcut, basestring) else
                    tuple(shortcut))
            if shortcut_name is None and spec[0]:
                shortcut_name = unicode(spec[0])

            if shortcut_name and self.action_spec[0] and not (
                    attr == 'qaction' and self.popup_type == QToolButton.InstantPopup):
                try:
                    self.gui.keyboard.register_shortcut(self.unique_name + ' - ' + attr,
                        shortcut_name, default_keys=keys,
                        action=shortcut_action, description=desc,
                        group=self.action_spec[0])
                except NameConflict as e:
                    try:
                        prints(unicode(e))
                    except:
                        pass
                    shortcut_action.setShortcuts([QKeySequence(key,
                        QKeySequence.PortableText) for key in keys])


        if attr is not None:
            setattr(self, attr, action)
        if attr == 'qaction' and self.action_add_menu:
            menu = QMenu()
            action.setMenu(menu)
            if self.action_menu_clone_qaction:
                menu.addAction(self.menuless_qaction)
        return action

    def create_menu_action(self, menu, unique_name, text, icon=None, shortcut=None,
            description=None, triggered=None, shortcut_name=None):
        '''
        Convenience method to easily add actions to a QMenu.
        Returns the created QAction, This action has one extra attribute
        calibre_shortcut_unique_name which if not None refers to the unique
        name under which this action is registered with the keyboard manager.

        :param menu: The QMenu the newly created action will be added to
        :param unique_name: A unique name for this action, this must be
            globally unique, so make it as descriptive as possible. If in doubt add
            a uuid to it.
        :param text: The text of the action.
        :param icon: Either a QIcon or a file name. The file name is passed to
            the I() builtin, so you do not need to pass the full path to the images
            directory.
        :param shortcut: A string, a list of strings, None or False. If False,
            no keyboard shortcut is registered for this action. If None, a keyboard
            shortcut with no default keybinding is registered. String and list of
            strings register a shortcut with default keybinding as specified.
        :param description: A description for this action. Used to set
            tooltips.
        :param triggered: A callable which is connected to the triggered signal
            of the created action.
        :param shortcut_name: The test displayed to the user when customizing
            the keyboard shortcuts for this action. By default it is set to the
            value of ``text``.

        '''
        if shortcut_name is None:
            shortcut_name = unicode(text)
        ac = menu.addAction(text)
        if icon is not None:
            if not isinstance(icon, QIcon):
                icon = QIcon(I(icon))
            ac.setIcon(icon)
        keys = ()
        if shortcut is not None and shortcut is not False:
            keys = ((shortcut,) if isinstance(shortcut, basestring) else
                    tuple(shortcut))
        unique_name = menu_action_unique_name(self, unique_name)
        if description is not None:
            ac.setToolTip(description)
            ac.setStatusTip(description)
            ac.setWhatsThis(description)

        ac.calibre_shortcut_unique_name = unique_name
        if shortcut is not False:
            self.gui.keyboard.register_shortcut(unique_name,
                shortcut_name, default_keys=keys,
                action=ac, description=description, group=self.action_spec[0])
        if triggered is not None:
            ac.triggered.connect(triggered)
        return ac

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
        available. The action specified by :attr:`action_spec` is available as
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

    def gui_layout_complete(self):
        '''
        Called once per action when the layout of the main GUI is
        completed. If your action needs to make changes to the layout, they
        should be done here, rather than in :meth:`initialization_complete`.
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
