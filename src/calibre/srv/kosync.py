#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, softwaregames1

# A server for the KOReader progress sync protocol, so that KOReader devices
# can sync reading positions via the calibre Content server. Users log in with
# the username and password of a Content server user. KOReader sends the MD5
# hash of the password as the key. The protocol is defined by the reference
# server at https://github.com/koreader/koreader-sync-server

import hmac
import json
import re
import time
from hashlib import md5

from calibre.srv.routes import endpoint
from calibre.srv.routes import json as json_postprocess

# The error codes and messages used by the reference server, KOReader displays
# the message to the user
UNAUTHORIZED = 401, 2001, 'Unauthorized'
TOO_MANY_ATTEMPTS = 403, 2001, 'Too many login attempts, try again later'
INVALID_REQUEST = 403, 2003, 'Invalid request'
DOCUMENT_MISSING = 403, 2004, "Field 'document' not provided."
REGISTRATION_DISABLED = 402, 2005, 'User registration is disabled. Log in with the username and password of a calibre Content server user.'
DOCUMENT_NOT_SERVABLE = 403, 2007, "Field 'document' contains characters the read route cannot serve."

document_pat = re.compile(r'[A-Za-z0-9_]+')


def error(rd, err):
    rd.status_code, code, message = err
    return {'code': code, 'message': message}


def authorized_user(ctx, rd) -> str | None:
    username = rd.inheaders.get('X-Auth-User', '')
    key = rd.inheaders.get('X-Auth-Key', '')
    if not username or not key or ':' in username:
        return None
    if not ctx.opts.auth:
        # Authentication is disabled, so the server is open to everyone anyway
        return username
    pw = ctx.user_manager.get(username)
    if pw is not None and hmac.compare_digest(md5(pw.encode('utf-8')).hexdigest(), key.lower()):
        return username
    # Count failures towards the same bans as other logins, so that passwords
    # cannot be guessed via these endpoints
    if (ac := getattr(ctx, 'auth_controller', None)) is not None:
        ac.ban_list.failed(rd.remote_addr)
    return None


def check_user(ctx, rd):
    # Return the authorized username or an error response
    if (ac := getattr(ctx, 'auth_controller', None)) is not None and ac.ban_list.is_banned(rd.remote_addr):
        return None, error(rd, TOO_MANY_ATTEMPTS)
    username = authorized_user(ctx, rd)
    if username is None:
        return None, error(rd, UNAUTHORIZED)
    return username, None


@endpoint('/kosync/healthcheck', auth_required=False, postprocess=json_postprocess, cache_control='no-cache')
def healthcheck(ctx, rd):
    return {'state': 'OK'}


@endpoint('/kosync/users/create', auth_required=False, methods=('POST',), postprocess=json_postprocess, cache_control='no-cache')
def create_user(ctx, rd):
    # Users are managed by calibre, not via KOReader
    return error(rd, REGISTRATION_DISABLED)


@endpoint('/kosync/users/auth', auth_required=False, postprocess=json_postprocess, cache_control='no-cache')
def auth_user(ctx, rd):
    username, err = check_user(ctx, rd)
    return err or {'authorized': 'OK'}


# PUT /kosync/syncs/progress stores progress, GET /kosync/syncs/progress/document
# returns it. They use a single endpoint since routes cannot differ only in a
# trailing variable.
@endpoint(
    '/kosync/syncs/progress/{document=""}',
    auth_required=False,
    methods=('GET', 'HEAD', 'PUT'),
    postprocess=json_postprocess,
    cache_control='no-cache',
)
def progress(ctx, rd, document):
    username, err = check_user(ctx, rd)
    if err is not None:
        return err
    if rd.method == 'PUT':
        return update_progress(ctx, rd, username)
    return get_progress(ctx, rd, username, document)


def update_progress(ctx, rd, username):
    try:
        data = json.load(rd.request_body_file)
    except ValueError:
        return error(rd, INVALID_REQUEST)
    if not isinstance(data, dict):
        return error(rd, INVALID_REQUEST)
    document = data.get('document')
    if not isinstance(document, str) or not document or ':' in document:
        return error(rd, DOCUMENT_MISSING)
    if document_pat.fullmatch(document) is None:
        return error(rd, DOCUMENT_NOT_SERVABLE)
    progress, device, device_id = data.get('progress'), data.get('device'), data.get('device_id')
    try:
        percentage = float(data.get('percentage'))
    except TypeError, ValueError:
        percentage = None
    if percentage is None or progress is None or not device:
        return error(rd, INVALID_REQUEST)
    metadata = data.get('metadata')
    timestamp = int(time.time())
    ctx.user_manager.set_kosync_progress(
        username,
        document,
        str(progress),
        percentage,
        str(device),
        None if device_id is None else str(device_id),
        timestamp,
        metadata if isinstance(metadata, dict) else None,
    )
    return {'document': document, 'timestamp': timestamp}


def get_progress(ctx, rd, username, document):
    if not document or ':' in document:
        return error(rd, DOCUMENT_MISSING)
    return ctx.user_manager.kosync_progress(username, document) or {}
