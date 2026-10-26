#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, softwaregames1

# A server for the KOReader progress sync protocol, so that KOReader devices
# can sync reading positions via the calibre Content server. Users log in with
# the username and password of a Content server user. KOReader sends the MD5
# hash of the password as the key. The protocol is defined by the reference
# server at https://github.com/koreader/koreader-sync-server

import hmac
import json
import math
import re
import time
from hashlib import md5

from calibre.srv.errors import HTTPForbidden
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
# Limit the size of the strings stored per document, KOReader sends MD5
# hashes and short XPointers
MAX_FIELD_LENGTH = 4096


def error(rd, err):
    rd.status_code, code, message = err
    return {'code': code, 'message': message}


def ban_key(rd) -> str:
    # Failed logins via these endpoints are banned separately from other
    # logins, so that a device retrying with a stale password in the background
    # does not lock out everyone sharing its IP address, such as all users of a
    # reverse proxy
    return 'kosync:' + rd.remote_addr


def log_warning(ctx, msg: str) -> None:
    if ctx.log is not None:
        ctx.log.warn(msg)


def authorized_user(ctx, rd) -> str | None:
    username = rd.inheaders.get('X-Auth-User', '')
    key = rd.inheaders.get('X-Auth-Key', '')
    # Header values that are not valid UTF-8 are bytes
    if not isinstance(username, str) or not isinstance(key, str) or not username or not key or ':' in username:
        return None
    if not ctx.opts.auth:
        # Authentication is disabled, so the server is open to everyone anyway
        return username
    pw = ctx.user_manager.get(username)
    # Always hash and compare, so that the response time does not reveal
    # whether the user exists
    expected = md5((pw or '').encode('utf-8')).hexdigest().encode('ascii')
    if hmac.compare_digest(expected, key.lower().encode('utf-8')) and pw is not None:
        return username
    log_warning(ctx, f'Failed KOReader sync login attempt from: {rd.remote_addr}')
    # Count failures towards bans, so that passwords cannot be guessed via
    # these endpoints
    if ctx.auth_controller is not None:
        ctx.auth_controller.ban_list.failed(ban_key(rd))
    return None


def check_user(ctx, rd):
    # Return the authorized username or an error response
    ac = ctx.auth_controller
    if ac is not None and (ac.ban_list.is_banned(rd.remote_addr) or ac.ban_list.is_banned(ban_key(rd))):
        log_warning(ctx, f'Too many KOReader sync login attempts from: {rd.remote_addr}')
        return None, error(rd, TOO_MANY_ATTEMPTS)
    username = authorized_user(ctx, rd)
    if username is None:
        return None, error(rd, UNAUTHORIZED)
    if ctx.opts.auth:
        # Used by check_for_write_access() and the access log
        rd.username = username
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


def valid_string(x) -> bool:
    return isinstance(x, str) and 0 < len(x) <= MAX_FIELD_LENGTH


def update_progress(ctx, rd, username):
    try:
        # Anonymous users may only make changes from trusted IP addresses and
        # readonly users not at all, as for the rest of the server
        ctx.check_for_write_access(rd)
    except HTTPForbidden as e:
        rd.status_code = e.http_code
        return {'code': 2001, 'message': str(e)}
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
    if len(document) > MAX_FIELD_LENGTH:
        return error(rd, INVALID_REQUEST)
    progress, device, device_id = data.get('progress'), data.get('device'), data.get('device_id')
    # KOReader sends page numbers as numbers for PDFs and XPointers as strings
    if isinstance(progress, (int, float)) and not isinstance(progress, bool):
        progress = str(progress)
    try:
        percentage = float(data.get('percentage'))
    except TypeError, ValueError, OverflowError:
        percentage = math.nan
    if not math.isfinite(percentage) or not valid_string(progress) or not valid_string(device):
        return error(rd, INVALID_REQUEST)
    if device_id is not None and not valid_string(device_id):
        return error(rd, INVALID_REQUEST)
    timestamp = int(time.time())
    ctx.user_manager.set_kosync_progress(username, document, progress, percentage, device, device_id, timestamp)
    return {'document': document, 'timestamp': timestamp}


def get_progress(ctx, rd, username, document):
    if not document or ':' in document:
        return error(rd, DOCUMENT_MISSING)
    return ctx.user_manager.kosync_progress(username, document) or {}
