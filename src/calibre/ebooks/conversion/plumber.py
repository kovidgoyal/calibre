from __future__ import with_statement
__license__ = 'GPL 3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os

from calibre.customize.conversion import OptionRecommendation 
from calibre.customize.ui import input_profiles, output_profiles, \
        plugin_for_input_format, plugin_for_output_format

class Plumber(object):
    
    pipeline_options = [

OptionRecommendation(name='verbose', 
            recommended_value=0, level=OptionRecommendation.LOW,
            short_switch='v', 
            help=_('Level of verbosity. Specify multiple times for greater '
                   'verbosity.')
        ),

OptionRecommendation(name='input_profile',
            recommended_value='default', level=OptionRecommendation.LOW,
            choices=[x.short_name for x in input_profiles()],
            help=_('Specify the input profile. The input profile gives the '
                   'conversion system information on how to interpret '
                   'various information in the input document. For '
                   'example resolution dependent lengths (i.e. lengths in '
                   'pixels).')
        ),

OptionRecommendation(name='output_profile',
            recommended_value='default', level=OptionRecommendation.LOW,
            choices=[x.short_name for x in output_profiles()],
            help=_('Specify the output profile. The output profile '
                   'tells the conversion system how to optimize the '
                   'created document for the specified device. In some cases, '
                   'an output profile is required to produce documents that '
                   'will work on a device. For example EPUB on the SONY reader.'
                   )
        ),

]

    def __init__(self, input, output, log):
        self.input = input
        self.output = output
        self.log = log
        
        input_fmt = os.path.splitext(input)[1]
        if not input_fmt:
            raise ValueError('Input file must have and extension')
        input_fmt = input_fmt[1:].lower()
        
        output_fmt = os.path.splitext(input)[1]
        if not output_fmt:
            output_fmt = '.oeb'
        output_fmt = output_fmt[1:].lower()
        
        self.input_plugin = plugin_for_input_format(input_fmt)
        self.output_plugin = plugin_for_output_format(output_fmt)
        
        if self.input_plugin is None:
            raise ValueError('No plugin to handle input format: '+input_fmt)
        
        if self.output_plugin is None:
            raise ValueError('No plugin to handle output format: '+output_fmt)
        
        self.input_fmt = input_fmt
        self.output_fmt = output_fmt
        
        self.input_options  = self.input_plugin.options.union(
                                    self.input_plugin.common_options)
        self.output_options = self.output_plugin.options.union(
                                    self.output_plugin.common_options)  
    
        self.merge_plugin_recommendations()

    def get_option_by_name(self, name):
        for group in (self.input_options, self.pipeline_options, 
                      self.output_options):
            for rec in group:
                if rec.option == name:
                    return rec
        
    def merge_plugin_recommendations(self):
        pass
    
    def merge_ui_recommendations(self, recommendations):
        pass
    
    
    
        