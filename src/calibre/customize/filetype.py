from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

from calibre.customize import Plugin as PluginBase

class Plugin(PluginBase):
    '''
    A plugin that is associated with a particular set of file types.
    '''
    
    #: List of file types for which this plugin should be run
    #: For example: ``['lit', 'mobi', 'prc']``
    file_types     = []
    
    #: If True, this plugin is run when books are added
    #: to the database
    on_import      = False
    
    #: If True, this plugin is run whenever an any2* tool
    #: is used, on the file passed to the any2* tool.
    on_preprocess  = False
    
    #: If True, this plugin is run after an any2* tool is
    #: used, on the final file produced by the tool.
    on_postprocess = False

    
