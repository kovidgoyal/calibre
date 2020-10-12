# -*- coding: utf-8 -*-


__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from io import BytesIO

from calibre.customize.conversion import InputFormatPlugin


class TCRInput(InputFormatPlugin):

    name        = 'TCR Input'
    author      = 'John Schember'
    description = 'Convert TCR files to HTML'
    file_types  = {'tcr'}
    commit_name = 'tcr_input'

    def convert(self, stream, options, file_ext, log, accelerators):
        from calibre.ebooks.compression.tcr import decompress

        log.info('Decompressing text...')
        raw_txt = decompress(stream)

        log.info('Converting text to OEB...')
        stream = BytesIO(raw_txt)

        from calibre.customize.ui import plugin_for_input_format

        txt_plugin = plugin_for_input_format('txt')
        for opt in txt_plugin.options:
            if not hasattr(self.options, opt.option.name):
                setattr(options, opt.option.name, opt.recommended_value)

        stream.seek(0)
        return txt_plugin.convert(stream, options,
                'txt', log, accelerators)
