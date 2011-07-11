#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from calibre.customize import Plugin

class InvalidEpub(ValueError):
    pass

class ParseError(ValueError):

    def __init__(self, name, desc):
        self.name = name
        self.desc = desc
        ValueError.__init__(self,
            _('Failed to parse: %(name)s with error: %(err)s')%dict(
                name=name, err=desc))

class ePubFixer(Plugin):

    supported_platforms = ['windows', 'osx', 'linux']
    author = 'Kovid Goyal'
    type = _('ePub Fixer')
    can_be_disabled = True

    # API that subclasses must implement {{{
    @property
    def short_description(self):
        raise NotImplementedError

    @property
    def long_description(self):
        raise NotImplementedError

    @property
    def fix_name(self):
        raise NotImplementedError

    @property
    def options(self):
        '''
        Return a list of 4-tuples
        (option_name, type, default, help_text)
        type is one of 'bool', 'int', 'string'
        '''
        return []

    def run(self, container, opts, log, fix=False):
        raise NotImplementedError
    # }}}

    def add_options_to_parser(self, parser):
        parser.add_option('--' + self.fix_name.replace('_', '-'),
                help=self.long_description, action='store_true', default=False)
        for option in self.options:
            action = 'store'
            if option[1] == 'bool':
                action = 'store_true'
            kwargs = {'action': action, 'default':option[2], 'help':option[3]}
            if option[1] != 'bool':
                kwargs['type'] = option[1]
            parser.add_option('--'+option[0].replace('_', '-'), **kwargs)

