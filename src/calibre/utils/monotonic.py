# vim:fileencoding=utf-8


try:
    from time import monotonic
except ImportError:
    from calibre.constants import plugins

    monotonicp, err = plugins['monotonic']
    if err:
        raise RuntimeError('Failed to load the monotonic module with error: ' + err)
    monotonic = monotonicp.monotonic
    del monotonicp, err
