# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

class StorePlugin(object): # {{{
    '''
    A plugin representing an online ebook repository (store). The store can
    be a comercial store that sells ebooks or a source of free downloadable
    ebooks.

    Note that this class is the base class for these plugins, however, to
    integrate the plugin with calibre's plugin system, you have to make a
    wrapper class that references the actual plugin. See the
    :mod:`calibre.customize.builtins` module for examples.

    If two :class:`StorePlugin` objects have the same name, the one with higher
    priority takes precedence.

    Sub-classes must implement :meth:`open`, and :meth:`search`.

    Regarding :meth:`open`. Most stores only make themselves available
    though a web site thus most store plugins will open using
    :class:`calibre.gui2.store.web_store_dialog.WebStoreDialog`. This will
    open a modal window and display the store website in a QWebView.

    Sub-classes should implement and use the :meth:`genesis` if they require
    plugin specific initialization. They should not override or otherwise
    reimplement :meth:`__init__`.

    Once initialized, this plugin has access to the main calibre GUI via the
    :attr:`gui` member. You can access other plugins by name, for example::

        self.gui.istores['Amazon Kindle']

    Plugin authors can use affiliate programs within their plugin. The
    distribution of money earned from a store plugin is 70/30. 70% going
    to the pluin author / maintainer and 30% going to the calibre project.

    The easiest way to handle affiliate money payouts is to randomly select
    between the author's affiliate id and calibre's affiliate id so that
    70% of the time the author's id is used.
    '''

    def __init__(self, gui, name):
        self.gui = gui
        self.name = name
        self.base_plugin = None

    def open(self, gui, parent=None, detail_item=None, external=False):
        '''
        Open the store.

        :param gui: The main GUI. This will be used to have the job
        system start downloading an item from the store.

        :param parent: The parent of the store dialog. This is used
        to create modal dialogs.

        :param detail_item: A plugin specific reference to an item
        in the store that the user should be shown.

        :param external: When False open an internal dialog with the
        store. When True open the users default browser to the store's
        web site. :param:`detail_item` should still be respected when external
        is True.
        '''
        raise NotImplementedError()

    def search(self, query, max_results=10, timeout=60):
        '''
        Searches the store for items matching query. This should
        return items as a generator.

        Don't be lazy with the search! Load as much data as possible in the
        :class:`calibre.gui2.store.search_result.SearchResult` object. 
        However, if data (such as cover_url)
        isn't available because the store does not display cover images then it's okay to
        ignore it.
        
        At the very least a :class:`calibre.gui2.store.search_result.SearchResult`
        returned by this function must have the title, author and id.
        
        If you have to parse multiple pages to get all of the data then implement
        :meth:`get_deatils` for retrieving additional information.

        Also, by default search results can only include ebooks. A plugin can offer users
        an option to include physical books in the search results but this must be
        disabled by default.

        If a store doesn't provide search on it's own use something like a site specific
        google search to get search results for this funtion.

        :param query: The string query search with.
        :param max_results: The maximum number of results to return.
        :param timeout: The maximum amount of time in seconds to spend download the search results.

        :return: :class:`calibre.gui2.store.search_result.SearchResult` objects
        item_data is plugin specific and is used in :meth:`open` to open to a specifc place in the store.
        '''
        raise NotImplementedError()
    
    def get_details(self, search_result, timeout=60):
        pass

    def get_settings(self):
        '''
        This is only useful for plugins that implement
        :attr:`config_widget` that is the only way to save
        settings. This is used by plugins to get the saved
        settings and apply when necessary.

        :return: A dictionary filled with the settings used
        by this plugin.
        '''
        raise NotImplementedError()

    def do_genesis(self):
        self.genesis()

    def genesis(self):
        '''
        Plugin specific initialization.
        '''
        pass

    def config_widget(self):
        '''
        See :class:`calibre.customize.Plugin` for details.
        '''
        raise NotImplementedError()

    def save_settings(self, config_widget):
        '''
        See :class:`calibre.customize.Plugin` for details.
        '''
        raise NotImplementedError()

    def customization_help(self, gui=False):
        '''
        See :class:`calibre.customize.Plugin` for details.
        '''
        raise NotImplementedError()

# }}}
