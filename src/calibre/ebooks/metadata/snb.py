'''Read meta information from SNB files'''


__license__   = 'GPL v3'
__copyright__ = '2010, Li Fanxi <lifanxi@freemindworld.com>'

import io
import os

from calibre.ebooks.metadata import MetaInformation
from calibre.ebooks.snb.snbfile import SNBFile
from calibre.utils.localization import _
from calibre.utils.xml_parse import safe_xml_fromstring


def get_metadata(stream, extract_cover=True):
    ''' Return metadata as a L{MetaInfo} object '''
    mi = MetaInformation(_('Unknown'), [_('Unknown')])
    snbFile = SNBFile()

    try:
        if not hasattr(stream, 'write'):
            snbFile.Parse(io.BytesIO(stream), True)
        else:
            stream.seek(0)
            snbFile.Parse(stream, True)

        meta = snbFile.GetFileStream('snbf/book.snbf')

        if meta is not None:
            meta = safe_xml_fromstring(meta)
            _name = meta.find('.//head/name')
            assert _name is not None
            mi.title = _name.text
            _author = meta.find('.//head/author')
            assert _author is not None
            mi.authors = [_author.text]
            _language = meta.find('.//head/language')
            assert _language is not None
            lang_text = _language.text
            assert lang_text is not None
            mi.language = lang_text.lower().replace('_', '-')
            _publisher = meta.find('.//head/publisher')
            assert _publisher is not None
            mi.publisher = _publisher.text

            if extract_cover:
                cover = meta.find('.//head/cover')
                if cover is not None and cover.text is not None:
                    root, ext = os.path.splitext(cover.text)
                    if ext == '.jpeg':
                        ext = '.jpg'
                    mi.cover_data = (ext[-3:], snbFile.GetFileStream('snbc/images/' + cover.text))

    except Exception:
        import traceback
        traceback.print_exc()

    return mi
