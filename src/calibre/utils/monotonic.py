# vim:fileencoding=utf-8

from calibre.constants import plugins

monotonicp, err = plugins['monotonic']
if err:
    raise RuntimeError('Failed to load the monotonic module with error: ' + err)
monotonic = monotonicp.monotonic
del monotonicp, err
