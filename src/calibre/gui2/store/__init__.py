# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

class StorePlugin(object): # {{{

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
        
        :param query: The string query search with.
        :param max_results: The maximum number of results to return.
        :param timeout: The maximum amount of time in seconds to spend download the search results.
        
        :return: :class:`calibre.gui2.store.search_result.SearchResult` objects
        item_data is plugin specific and is used in :meth:`open` to open to a specifc place in the store.
        '''
        raise NotImplementedError()
    
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
        pass
    
    def config_widget(self):
        raise NotImplementedError()
    
    def save_settings(self, config_widget):
        raise NotImplementedError()
    
    def customization_help(self, gui=False):
        raise NotImplementedError()

# }}}