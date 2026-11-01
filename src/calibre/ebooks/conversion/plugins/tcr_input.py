# License: GPLv3 Copyright: 2009, John Schember <john@nachtimwald.com>

from io import BytesIO
from typing import IO, TYPE_CHECKING

from calibre.customize.conversion import InputFormatPlugin
from calibre.utils.localization import _

if TYPE_CHECKING:
    from optparse import Values

    from calibre.ebooks.oeb.base import OEBBook
    from calibre.utils.logging import Log


class TCRInput(InputFormatPlugin):
    name = 'TCR Input'
    author = 'John Schember'
    description = _('Convert TCR files to HTML')
    file_types = {'tcr'}
    commit_name = 'tcr_input'

    def convert(self, stream: IO[bytes], options: Values, file_ext: str, log: Log, accelerators: dict[str, str]) -> str | OEBBook | None:
        from calibre.ebooks.compression.tcr import decompress

        log.info('Decompressing text...')
        raw_txt = decompress(stream)

        log.info('Converting text to OEB...')
        stream = BytesIO(raw_txt)

        from calibre.customize.ui import plugin_for_input_format

        txt_plugin = plugin_for_input_format('txt')
        assert txt_plugin is not None
        for opt in txt_plugin.options:
            if not hasattr(options, opt.option.name):
                setattr(options, opt.option.name, opt.recommended_value)

        stream.seek(0)
        return txt_plugin.convert(stream, options, 'txt', log, accelerators)
