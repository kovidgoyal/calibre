#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>


'''
OAuth 2.0 authentication for SMTP email sending (PKCE flow).
'''

import base64
import hashlib
import json
import os
import socket
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

from calibre import browser as get_browser


class OAuth2Error(Exception):
    pass


def generate_pkce_pair():
    code_verifier = base64.urlsafe_b64encode(os.urandom(32)).decode('utf-8').rstrip('=')
    code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode('utf-8')).digest()).decode('utf-8').rstrip('=')
    return code_verifier, code_challenge


def generate_xoauth2_string(email, access_token):
    # Format: user={email}\x01auth=Bearer {token}\x01\x01
    auth_string = f'user={email}\x01auth=Bearer {access_token}\x01\x01'
    return base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')


def find_available_port(start_port=8080, max_attempts=10):
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('localhost', port))
                return port
        except OSError:
            continue
    return None


class OAuth2Provider:

    name = None
    client_id = None
    client_secret = None
    auth_url = None
    token_url = None
    scopes = []

    def __init__(self, redirect_uri=None):
        self.redirect_uri = redirect_uri or 'http://localhost:8080/oauth2callback'

    def get_authorization_url(self, state, code_challenge):
        params = {
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'response_type': 'code',
            'scope': ' '.join(self.scopes),
            'state': state,
            'code_challenge': code_challenge,
            'code_challenge_method': 'S256',
            'access_type': 'offline',
            'prompt': 'consent',
        }
        return f'{self.auth_url}?{urlencode(params)}'

    def exchange_code_for_tokens(self, code, code_verifier):
        br = get_browser()
        data = {
            'client_id': self.client_id,
            'code': code,
            'code_verifier': code_verifier,
            'grant_type': 'authorization_code',
            'redirect_uri': self.redirect_uri,
        }
        if self.client_secret is not None:
            data['client_secret'] = self.client_secret

        try:
            response = br.open_novisit(self.token_url, data=urlencode(data).encode('utf-8'), timeout=30)
            result = json.loads(response.read())

            if 'error' in result:
                error_msg = result.get('error_description', result['error'])
                if 'redirect_uri_mismatch' in result.get('error', ''):
                    error_msg += f'\nRedirect URI: {self.redirect_uri}'
                elif 'invalid_client' in result.get('error', ''):
                    error_msg += f'\nClient ID: {self.client_id}'
                raise OAuth2Error(f'Token exchange failed: {error_msg}')

            result['expires_at'] = int(time.time()) + result.get('expires_in', 3600)
            return result
        except Exception as e:
            if isinstance(e, OAuth2Error):
                raise
            error_body = ''
            if hasattr(e, 'read'):
                try:
                    error_body = e.read()
                    if isinstance(error_body, bytes):
                        error_body = error_body.decode('utf-8', 'replace')
                except Exception:
                    pass
            if error_body:
                try:
                    err_json = json.loads(error_body)
                    error_details = err_json.get('error_description') or err_json.get('error') or error_body
                except json.JSONDecodeError:
                    error_details = error_body
            else:
                error_details = str(e)
            raise OAuth2Error(f'Token exchange failed: {error_details}')

    def refresh_access_token(self, refresh_token):
        br = get_browser()
        data = {
            'client_id': self.client_id,
            'refresh_token': refresh_token,
            'grant_type': 'refresh_token',
        }
        if self.client_secret is not None:
            data['client_secret'] = self.client_secret
        try:
            response = br.open_novisit(self.token_url, data=urlencode(data).encode('utf-8'), timeout=30)
            result = json.loads(response.read())
            if 'error' in result:
                raise OAuth2Error(f'Token refresh failed: {result.get("error_description", result["error"])}')
            result['expires_at'] = int(time.time()) + result.get('expires_in', 3600)
            if 'refresh_token' not in result:
                result['refresh_token'] = refresh_token
            return result
        except OAuth2Error:
            raise
        except Exception as e:
            raise OAuth2Error(f'Token refresh failed: {e}')


class GmailOAuth2Provider(OAuth2Provider):
    name = 'gmail'
    client_id = os.environ.get('CALIBRE_GMAIL_CLIENT_ID', '410090137009-6f4jgjvsvcmtr1kqbtcro2j76rb7pio4.apps.googleusercontent.com')
    client_secret = os.environ.get('CALIBRE_GMAIL_CLIENT_SECRET', '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')
    auth_url = 'https://accounts.google.com/o/oauth2/v2/auth'
    token_url = 'https://oauth2.googleapis.com/token'
    scopes = ['https://mail.google.com/']


class OutlookOAuth2Provider(OAuth2Provider):
    name = 'outlook'
    client_id = os.environ.get('CALIBRE_OUTLOOK_CLIENT_ID', '')  # register at portal.azure.com
    client_secret = os.environ.get('CALIBRE_OUTLOOK_CLIENT_SECRET')
    auth_url = 'https://login.microsoftonline.com/common/oauth2/v2.0/authorize'
    token_url = 'https://login.microsoftonline.com/common/oauth2/v2.0/token'
    scopes = ['https://outlook.office.com/SMTP.Send', 'offline_access']


PROVIDERS = {
    'gmail': GmailOAuth2Provider,
    'outlook': OutlookOAuth2Provider,
}

PROVIDER_DISPLAY_NAMES = {'gmail': 'Gmail', 'outlook': 'Outlook/Hotmail/Office 365'}


def get_provider(provider_name):
    if provider_name not in PROVIDERS:
        raise OAuth2Error(f'Unknown OAuth provider: {provider_name}')
    return PROVIDERS[provider_name]()


def get_available_providers():
    return [(name, PROVIDER_DISPLAY_NAMES.get(name, name))
            for name, cls in PROVIDERS.items() if cls.client_id]


def is_provider_available(provider_name):
    return provider_name in PROVIDERS and bool(PROVIDERS[provider_name].client_id)


class OAuth2CallbackHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path != '/oauth2callback':
            self.send_error(404)
            return

        query = parse_qs(parsed.query)

        if 'error' in query:
            self.server.oauth_error = query['error'][0]
            error_desc = query.get('error_description', [''])[0]
            html = f'''
            <html>
            <head>
                <meta charset="UTF-8">
                <title>Authorization Failed</title>
                <style>
                    body {{ font-family: sans-serif; text-align: center; padding: 50px; }}
                    h1 {{ color: #c62828; }}
                </style>
            </head>
            <body>
                <h1>Authorization Failed</h1>
                <p>Error: {self.server.oauth_error}</p>
                <p>{error_desc}</p>
                <p>You can close this window.</p>
            </body>
            </html>
            '''
        elif 'code' in query and 'state' in query:
            self.server.authorization_code = query['code'][0]
            self.server.state = query['state'][0]
            html = '''
            <html>
            <head>
                <meta charset="UTF-8">
                <title>Authorization Successful</title>
                <style>
                    body { font-family: sans-serif; text-align: center; padding: 50px; }
                    h1 { color: #2e7d32; }
                </style>
            </head>
            <body>
                <h1>Authorization Successful!</h1>
                <p>You can close this window and return to calibre.</p>
            </body>
            </html>
            '''
        else:
            self.send_error(400, 'Missing required parameters')
            return

        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))
        threading.Thread(target=self.server.shutdown).start()


class OAuth2BrowserFlow:

    def __init__(self, provider, start_port=8080):
        self.provider = provider
        self.start_port = start_port

    def start_authorization_flow(self, timeout=300):
        port = find_available_port(start_port=self.start_port)
        if port is None:
            raise OAuth2Error(f'No available port for OAuth callback (tried {self.start_port}-{self.start_port + 9})')

        self.provider.redirect_uri = f'http://localhost:{port}/oauth2callback'
        code_verifier, code_challenge = generate_pkce_pair()
        state = base64.urlsafe_b64encode(os.urandom(32)).decode('utf-8').rstrip('=')
        auth_url = self.provider.get_authorization_url(state, code_challenge)

        server = HTTPServer(('localhost', port), OAuth2CallbackHandler)
        server.oauth_error = None
        server.authorization_code = None
        server.state = None

        if not webbrowser.open(auth_url):
            raise OAuth2Error(f'Failed to open browser. Please open: {auth_url}')

        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.daemon = True
        server_thread.start()

        start_time = time.time()
        while server_thread.is_alive() and (time.time() - start_time) < timeout:
            time.sleep(0.5)

        if server_thread.is_alive():
            server.shutdown()
            raise OAuth2Error(f'Authorization timeout after {timeout} seconds')
        if server.oauth_error:
            raise OAuth2Error(f'Authorization failed: {server.oauth_error}')
        if not server.authorization_code:
            raise OAuth2Error('No authorization code received')
        if server.state != state:
            raise OAuth2Error('State mismatch - possible CSRF attack')

        return self.provider.exchange_code_for_tokens(server.authorization_code, code_verifier)


class OAuth2TokenManager:

    def __init__(self, provider, tokens=None):
        self.provider = provider
        self.tokens = tokens or {}

    def get_valid_token(self):
        if not self.tokens:
            raise OAuth2Error('No tokens available. Please authorize first.')
        expires_at = self.tokens.get('expires_at', 0)
        if time.time() >= (expires_at - 300):  # 5 min buffer
            if 'refresh_token' not in self.tokens:
                raise OAuth2Error('No refresh token available. Please re-authorize.')
            self.tokens = self.provider.refresh_access_token(self.tokens['refresh_token'])
        return self.tokens

    def is_valid(self):
        if not self.tokens or 'access_token' not in self.tokens:
            return False
        return time.time() < (self.tokens.get('expires_at', 0) - 300)


def start_oauth_flow(provider_name, start_port=8080):
    flow = OAuth2BrowserFlow(get_provider(provider_name), start_port=start_port)
    return flow.start_authorization_flow()


def get_token_manager(provider_name, tokens=None):
    return OAuth2TokenManager(get_provider(provider_name), tokens)


def refresh_token_if_needed(provider_name, tokens):
    token_mgr = get_token_manager(provider_name, tokens)
    new_tokens = token_mgr.get_valid_token()
    return new_tokens, new_tokens != tokens
