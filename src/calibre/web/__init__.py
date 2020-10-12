

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'


class Recipe(object):
    pass


def get_download_filename_from_response(response):
    from polyglot.urllib import unquote, urlparse
    filename = last_part_name = ''
    try:
        purl = urlparse(response.geturl())
        last_part_name = unquote(purl.path.split('/')[-1])
        disposition = response.info().get('Content-disposition', '')
        if isinstance(disposition, bytes):
            disposition = disposition.decode('utf-8', 'replace')
        for p in disposition.split(';'):
            if 'filename' in p:
                if '*=' in disposition:
                    parts = disposition.split('*=')[-1]
                    filename = parts.split('\'')[-1]
                else:
                    filename = disposition.split('=')[-1]
                if filename[0] in ('\'', '"'):
                    filename = filename[1:]
                if filename[-1] in ('\'', '"'):
                    filename = filename[:-1]
                filename = unquote(filename)
                break
    except Exception:
        import traceback
        traceback.print_exc()
    return filename or last_part_name


def get_download_filename(url, cookie_file=None):
    '''
    Get a local filename for a URL using the content disposition header
    Returns empty string if an error occurs.
    '''
    from calibre import browser
    from contextlib import closing

    filename = ''

    br = browser()
    if cookie_file:
        from mechanize import MozillaCookieJar
        cj = MozillaCookieJar()
        cj.load(cookie_file)
        br.set_cookiejar(cj)

    try:
        with closing(br.open(url)) as r:
            filename = get_download_filename_from_response(r)
    except:
        import traceback
        traceback.print_exc()

    return filename
