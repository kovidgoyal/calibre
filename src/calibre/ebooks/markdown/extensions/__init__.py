"""
Extensions
-----------------------------------------------------------------------------
"""

from __future__ import unicode_literals
from ..util import parseBoolValue
import warnings


class Extension(object):
    """ Base class for extensions to subclass. """

    # Default config -- to be overriden by a subclass
    # Must be of the following format:
    #     {
    #       'key': ['value', 'description']
    #     }
    # Note that Extension.setConfig will raise a KeyError
    # if a default is not set here.
    config = {}

    def __init__(self, *args, **kwargs):
        """ Initiate Extension and set up configs. """

        # check for configs arg for backward compat.
        # (there only ever used to be one so we use arg[0])
        if len(args):
            if args[0] is not None:
                self.setConfigs(args[0])
            warnings.warn('Extension classes accepting positional args is '
                          'pending Deprecation. Each setting should be '
                          'passed into the Class as a keyword. Positional '
                          'args are deprecated and will raise '
                          'an error in version 2.7. See the Release Notes for '
                          'Python-Markdown version 2.6 for more info.',
                          DeprecationWarning)
        # check for configs kwarg for backward compat.
        if 'configs' in kwargs.keys():
            if kwargs['configs'] is not None:
                self.setConfigs(kwargs.pop('configs', {}))
            warnings.warn('Extension classes accepting a dict on the single '
                          'keyword "config" is pending Deprecation. Each '
                          'setting should be passed into the Class as a '
                          'keyword directly. The "config" keyword is '
                          'deprecated and raise an error in '
                          'version 2.7. See the Release Notes for '
                          'Python-Markdown version 2.6 for more info.',
                          DeprecationWarning)
        # finally, use kwargs
        self.setConfigs(kwargs)

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
        if isinstance(self.config[key][0], bool):
            value = parseBoolValue(value)
        if self.config[key][0] is None:
            value = parseBoolValue(value, preserve_none=True)
        self.config[key][0] = value

    def setConfigs(self, items):
        """ Set multiple config settings given a dict or list of tuples. """
        if hasattr(items, 'items'):
            # it's a dict
            items = items.items()
        for key, value in items:
            self.setConfig(key, value)

    def extendMarkdown(self, md, md_globals):
        """
        Add the various proccesors and patterns to the Markdown Instance.

        This method must be overriden by every extension.

        Keyword arguments:

        * md: The Markdown instance.

        * md_globals: Global variables in the markdown module namespace.

        """
        raise NotImplementedError(
            'Extension "%s.%s" must define an "extendMarkdown"'
            'method.' % (self.__class__.__module__, self.__class__.__name__)
        )
