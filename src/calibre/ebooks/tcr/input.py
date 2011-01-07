# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from cStringIO import StringIO

from calibre.customize.conversion import InputFormatPlugin, OptionRecommendation
from calibre.ebooks.compression.tcr import decompress

class TCRInput(InputFormatPlugin):

    name        = 'TCR Input'
    author      = 'John Schember'
    description = 'Convert TCR files to HTML'
    file_types  = set(['tcr'])

    def convert(self, stream, options, file_ext, log, accelerators):
        log.info('Decompressing text...')
        raw_txt = decompress(stream)

        log.info('Converting text to OEB...')
        stream = StringIO(raw_txt)

        from calibre.customize.ui import plugin_for_input_format

        txt_plugin = plugin_for_input_format('txt')
        for option in txt_plugin.options:
            if not hasattr(options, option.option.name):
                setattr(options, option.name, option.recommended_value)

        stream.seek(0)
        return txt_plugin.convert(stream, options,
                'txt', log, accelerators)
