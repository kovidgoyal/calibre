__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from calibre.utils.filenames import ascii_filename


class StorePlugin:  # {{{

    '''
    A plugin representing an online ebook repository (store). The store can
    be a commercial store that sells ebooks or a source of free downloadable
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

    See declined.txt for a list of stores that do not want to be included.
    '''

    minimum_calibre_version = (0, 9, 14)

    def __init__(self, gui, name, config=None, base_plugin=None):
        self.gui = gui
        self.name = name
        self.base_plugin = base_plugin
        if config is None:
            from calibre.utils.config import JSONConfig
            config = JSONConfig('store/stores/' + ascii_filename(self.name))
        self.config = config

    def create_browser(self):
        '''
        If the server requires special headers, such as a particular user agent
        or a referrer, then implement this method in your plugin to return a
        customized browser instance. See the Gutenberg plugin for an example.

        Note that if you implement the open() method in your plugin and use the
        WebStoreDialog class, remember to pass self.createbrowser in the
        constructor of WebStoreDialog.
        '''
        raise NotImplementedError()

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
        google search to get search results for this function.

        :param query: The string query search with.
        :param max_results: The maximum number of results to return.
        :param timeout: The maximum amount of time in seconds to spend downloading data for search results.

        :return: :class:`calibre.gui2.store.search_result.SearchResult` objects
        item_data is plugin specific and is used in :meth:`open` to open to a specific place in the store.
        '''
        raise NotImplementedError()

    def get_details(self, search_result, timeout=60):
        '''
        Delayed search for information about specific search items.

        Typically, this will be used when certain information such as
        formats, drm status, cover url are not part of the main search
        results and the information is on another web page.

        Using this function allows for the main information (title, author)
        to be displayed in the search results while other information can
        take extra time to load. Splitting retrieving data that takes longer
        to load into a separate function will give the illusion of the search
        being faster.

        :param search_result: A search result that need details set.
        :param timeout: The maximum amount of time in seconds to spend downloading details.

        :return: True if the search_result was modified otherwise False
        '''
        return False

    def update_cache(self, parent=None, timeout=60, force=False, suppress_progress=False):
        '''
        Some plugins need to keep an local cache of available books. This function
        is called to update the caches. It is recommended to call this function
        from :meth:`open`. Especially if :meth:`open` does anything other than
        open a web page.

        This function can be called at any time. It is up to the plugin to determine
        if the cache really does need updating. Unless :param:`force` is True, then
        the plugin must update the cache. The only time force should be True is if
        this function is called by the plugin's configuration dialog.

        if :param:`suppress_progress` is False it is safe to assume that this function
        is being called from the main GUI thread so it is safe and recommended to use
        a QProgressDialog to display what is happening and allow the user to cancel
        the operation. if :param:`suppress_progress` is True then run the update
        silently. In this case there is no guarantee what thread is calling this
        function so no Qt related functionality that requires being run in the main
        GUI thread should be run. E.G. Open a QProgressDialog.

        :param parent: The parent object to be used by an GUI dialogs.

        :param timeout: The maximum amount of time that should be spent in
        any given network connection.

        :param force: Force updating the cache even if the plugin has determined
        it is not necessary.

        :param suppress_progress: Should a progress indicator be shown.

        :return: True if the cache was updated, False otherwise.
        '''
        return False

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
