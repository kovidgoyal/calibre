from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

class Plugin(object):
    
    #: List of platforms this plugin works on
    #: For example: ``['windows', 'osx', 'linux']
    supported_platforms = []
    
    #: The name of this plugin
    name           = 'Trivial Plugin'
    
    #: The version of this plugin as a 3-tuple (major, minor, revision)
    version        = (1, 0, 0)
    
    #: A short string describing what this plugin does
    description    = _('Does absolutely nothing')
    
    #: The author of this plugin
    author         = _('Unknown')
    
    #: When more than one plugin exists for a filetype,
    #: the plugins are run in order of decreasing priority
    #: i.e. plugins with higher priority will be run first.
    #: The highest possible priority is ``sys.maxint``.
    #: Default pririty is 1.
    priority = 1
    
    #: The earliest version of calibre this plugin requires
    minimum_calibre_version = (0, 4, 118)

    def __init__(self, plugin_path):
        '''
        Called once when calibre plugins are initialized. Plugins are re-initialized
        every time a new plugin is added.
        
        :param plugin_path: Path to the zip file this plugin is distributed in.
        '''
        self.plugin_path = plugin_path
        
    def customization_help(self):
        '''
        Return a string giving help on how to customize this plugin.
        By default raise a :class:`NotImplementedError`, which indicates that
        the plugin does not require customization. 
        '''
        raise NotImplementedError
        
    def run(self, path_to_ebook, site_customization=''):
        '''
        Run the plugin. Must be implemented in subclasses.
        It should perform whatever modifications are required 
        on the ebook and return the absolute path to the 
        modified ebook. If no modifications are needed, it should
        return the path to the original ebook. If an error is encountered
        it should raise an Exception. The default implementation
        simply return the path to the original ebook.
        
        :param path_to_ebook: Absolute path to the ebook
        :param site_customization: A (possibly empty) string that the user
                                   has specified to customize this plugin.
                                   For example, it could be the path to a needed
                                   executable on her system.
                                   
        :return: Absolute path to the modified ebook. 
        '''
        # Default implementation does nothing
        return path_to_ebook 