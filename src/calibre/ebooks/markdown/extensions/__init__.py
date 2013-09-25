"""
Extensions
-----------------------------------------------------------------------------
"""

from __future__ import unicode_literals

class Extension(object):
    """ Base class for extensions to subclass. """
    def __init__(self, configs = {}):
        """Create an instance of an Extention.

        Keyword arguments:

        * configs: A dict of configuration setting used by an Extension.
        """
        self.config = configs

    def getConfig(self, key, default=''):
        """ Return a setting for the given key or an empty string. """
        if key in self.config:
            return self.config[key][0]
        else:
            return default

    def getConfigs(self):
        """ Return all configs settings as a dict. """
        return dict([(key, self.getConfig(key)) for key in self.config.keys()])

    def getConfigInfo(self):
        """ Return all config descriptions as a list of tuples. """
        return [(key, self.config[key][1]) for key in self.config.keys()]

    def setConfig(self, key, value):
        """ Set a config setting for `key` with the given `value`. """
        self.config[key][0] = value

    def extendMarkdown(self, md, md_globals):
        """
        Add the various proccesors and patterns to the Markdown Instance.

        This method must be overriden by every extension.

        Keyword arguments:

        * md: The Markdown instance.

        * md_globals: Global variables in the markdown module namespace.

        """
        raise NotImplementedError('Extension "%s.%s" must define an "extendMarkdown"' \
            'method.' % (self.__class__.__module__, self.__class__.__name__))

