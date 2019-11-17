#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

# License: GPLv3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>

if False:
    # This is here to keep my python error checker from complaining about
    # the builtin functions that will be defined by the plugin loading system
    # You do not need this code in your plugins
    get_icons = get_resources = None

# The class that all interface action plugins must inherit from
from calibre.gui2.actions import InterfaceAction
from PyQt5.Qt import QInputDialog


class InterfacePlugin(InterfaceAction):

    name = 'WebEngine Plugin Demo'

    # Declare the main action associated with this plugin
    # The keyboard shortcut can be None if you dont want to use a keyboard
    # shortcut. Remember that currently calibre has no central management for
    # keyboard shortcuts, so try to use an unusual/unused shortcut.
    action_spec = ('WebEngine Plugin Demo', None,
            'Run the WebEngine Plugin Demo', 'Ctrl+Shift+F2')

    def genesis(self):
        # This method is called once per plugin, do initial setup here

        # Set the icon for this interface action
        # The get_icons function is a builtin function defined for all your
        # plugin code. It loads icons from the plugin zip file. It returns
        # QIcon objects, if you want the actual data, use the analogous
        # get_resources builtin function.
        #
        # Note that if you are loading more than one icon, for performance, you
        # should pass a list of names to get_icons. In this case, get_icons
        # will return a dictionary mapping names to QIcons. Names that
        # are not found in the zip file will result in null QIcons.
        icon = get_icons('images/icon.png')

        # The qaction is automatically created from the action_spec defined
        # above
        self.qaction.setIcon(icon)
        self.qaction.triggered.connect(self.show_dialog)

    def show_dialog(self):
        # Ask the user for a URL
        url, ok = QInputDialog.getText(self.gui, 'Enter a URL', 'Enter a URL to browse below', text='https://calibre-ebook.com')
        if not ok or not url:
            return
        # Launch a separate process to view the URL in WebEngine
        self.gui.job_manager.launch_gui_app('webengine-dialog', kwargs={
            'module':'calibre_plugins.webengine_demo.main', 'url':url})
