'''
Defines the plugin sytem for conversions.
'''
import re

from calibre.customize import Plugin


class ConversionOption(object):
    
    '''
    Class representing conversion options
    '''
    
    def __init__(self, name=None, default=None, help=None, long_switch=None, 
                 short_switch=None, choices=None, gui_label=None, 
                 category=None):
        self.name = name
        self.default = default
        self.help = help
        self.long_switch = long_switch
        self.short_switch = short_switch
        self.choices = choices
        self.gui_label = gui_label
        self.category = category
        
        self.validate_parameters()
        
    def validate_parameters(self):
        '''
        Validate the parameters passed to :method:`__init__`.
        '''
        if re.match(r'[a-zA-Z_]([a-zA-Z0-9_])*', self.name) is None:
            raise ValueError(self.name + ' is not a valid Python identifier')
        if not (isinstance(self.default, (int, float, str, unicode)) or \
            self.default is None):
            raise ValueError(unicode(self.default) + 
                             ' is not a string or a number')
        if not self.help:
            raise ValueError('You must set the help text')      

class ConversionPlugin(Plugin):
    
    '''
    The base class for all conversion related plugins.
    '''
    #: List of options
    #: Each option must be a dictionary. The dictionary can contain several
    #: keys defining the option. The ones marked by a * are required, the rest
    #: are optional. The keys are::
    #:
    #:    *'name'        : A valid python identifier.
    #:    *'default'     : The default value for this option.
    #:    *'help'        : 
    #:    'short_switch' : A suggestion for a short form of the command line
    #:                     switch (for example if name is 'title', this 
    #:                     could be 't'). It is only used if no prior
    #:                     conversion plugin has claimed it. 
    options = []
    
    type = _('Conversion')
    can_be_disabled = False
    supported_platforms = ['windows', 'osx', 'linux']
    

class InputFormatPlugin(ConversionPlugin):
    
    #: Set of file types for which this plugin should be run
    #: For example: ``set(['lit', 'mobi', 'prc'])``
    file_types     = set([])
    
 
