#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

from calibre import as_unicode
from calibre.db.cli import module_for_cmd
from calibre.srv.errors import HTTPNotFound, HTTPBadRequest
from calibre.srv.routes import endpoint, msgpack_or_json
from calibre.srv.utils import get_library_data
from calibre.utils.serialize import MSGPACK_MIME, msgpack_loads, json_loads

receive_data_methods = {'GET', 'POST'}


@endpoint('/cdb/cmd/{which}/{version=0}', postprocess=msgpack_or_json, methods=receive_data_methods)
def cdb_run(ctx, rd, which, version):
    try:
        m = module_for_cmd(which)
    except ImportError:
        raise HTTPNotFound('No module named: {}'.format(which))
    if not getattr(m, 'readonly', False):
        ctx.check_for_write_access(rd)
    if getattr(m, 'version', 0) != int(version):
        raise HTTPNotFound(('The module {} is not available in version: {}.'
                           'Make sure the version of calibre used for the'
                            ' server and calibredb match').format(which, version))
    raw = rd.read()
    ct = rd.inheaders.get('Content-Type', all=True)
    try:
        if MSGPACK_MIME in ct:
            args = msgpack_loads(raw)
        else:
            args = json_loads(raw)
    except Exception:
        raise HTTPBadRequest('args are not valid encoded data')
    db = get_library_data(ctx, rd, strict_library_id=True)[0]
    try:
        result = m.implementation(db, ctx.notify_changes, *args)
    except Exception as err:
        import traceback
        return {'err': as_unicode(err), 'tb': traceback.format_exc()}
    return {'result': result}
