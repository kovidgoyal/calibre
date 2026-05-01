#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Calibre Contributors

'''
Audiobookshelf API client for syncing libraries between Calibre and
an Audiobookshelf server instance. Handles:
- Library item discovery and metadata sync
- Listening progress sync (bidirectional)
- Cover art download
- Audiobook file download for offline playback
'''

import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen


class AudiobookshelfClient:
    '''
    Client for the Audiobookshelf REST API.
    '''

    def __init__(self, server_url, api_token=None, username=None, password=None, timeout=30):
        self.server_url = server_url.rstrip('/')
        self.api_token = api_token
        self.timeout = timeout
        if not api_token and username and password:
            self.api_token = self._login(username, password)

    def _login(self, username, password):
        '''Authenticate and obtain API token.'''
        data = json.dumps({'username': username, 'password': password}).encode()
        resp = self._request('POST', '/login', data=data, auth=False)
        return resp.get('user', {}).get('token', '')

    def _request(self, method, path, data=None, params=None, auth=True):
        '''Make an API request.'''
        url = self.server_url + '/api' + path
        if params:
            url += '?' + urlencode(params)

        headers = {'Content-Type': 'application/json'}
        if auth and self.api_token:
            headers['Authorization'] = f'Bearer {self.api_token}'

        req = Request(url, data=data, headers=headers, method=method)
        try:
            with urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode())
        except HTTPError as e:
            body = e.read().decode() if e.fp else ''
            raise ConnectionError(f'API error {e.code} for {method} {path}: {body[:200]}') from e
        except URLError as e:
            raise ConnectionError(f'Cannot connect to {self.server_url}: {e.reason}') from e

    def _download(self, path, dest_path):
        '''Download a file from the server.'''
        url = self.server_url + path
        headers = {}
        if self.api_token:
            headers['Authorization'] = f'Bearer {self.api_token}'
        req = Request(url, headers=headers)
        with urlopen(req, timeout=self.timeout) as resp:
            with open(dest_path, 'wb') as f:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)

    # --- Library operations ---

    def get_libraries(self):
        '''List all libraries.'''
        return self._request('GET', '/libraries').get('libraries', [])

    def get_library_items(self, library_id, limit=100, page=0, sort='media.metadata.title',
                          filter_type=None, minified=True):
        '''Get items in a library with pagination.'''
        params = {'limit': limit, 'page': page, 'sort': sort}
        if minified:
            params['minified'] = 1
        if filter_type:
            params['filter'] = filter_type
        return self._request('GET', f'/libraries/{library_id}/items', params=params)

    def get_item(self, item_id, expanded=True):
        '''Get full details for a library item.'''
        params = {'expanded': 1} if expanded else {}
        return self._request('GET', f'/items/{item_id}', params=params)

    def search(self, library_id, query, limit=10):
        '''Search a library.'''
        params = {'q': query, 'limit': limit}
        return self._request('GET', f'/libraries/{library_id}/search', params=params)

    # --- Progress operations ---

    def get_progress(self, item_id):
        '''Get listening progress for current user on an item.'''
        return self._request('GET', f'/me/progress/{item_id}')

    def update_progress(self, item_id, current_time, duration=None, is_finished=False):
        '''Update listening progress.'''
        data = {'currentTime': current_time, 'isFinished': is_finished}
        if duration is not None:
            data['duration'] = duration
        return self._request('PATCH', f'/me/progress/{item_id}',
                             data=json.dumps(data).encode())

    def get_all_progress(self):
        '''Get all media progress for current user.'''
        me = self._request('GET', '/me')
        return me.get('mediaProgress', [])

    # --- Playback session ---

    def start_session(self, item_id, device_info=None):
        '''Start a playback session and get audio tracks.'''
        data = {
            'deviceInfo': device_info or {
                'clientName': 'calibre',
                'clientVersion': '1.0',
            },
            'supportedMimeTypes': ['audio/mpeg', 'audio/mp4', 'audio/ogg', 'audio/flac'],
        }
        return self._request('POST', f'/items/{item_id}/play',
                             data=json.dumps(data).encode())

    def sync_session(self, session_id, current_time, time_listened=0):
        '''Sync playback session progress.'''
        data = {'currentTime': current_time, 'timeListening': time_listened}
        return self._request('POST', f'/session/{session_id}/sync',
                             data=json.dumps(data).encode())

    def close_session(self, session_id, current_time=None, time_listened=None):
        '''Close a playback session.'''
        data = {}
        if current_time is not None:
            data['currentTime'] = current_time
        if time_listened is not None:
            data['timeListening'] = time_listened
        return self._request('POST', f'/session/{session_id}/close',
                             data=json.dumps(data).encode())

    # --- Cover art ---

    def download_cover(self, item_id, dest_path):
        '''Download cover art for an item.'''
        self._download(f'/api/items/{item_id}/cover', dest_path)

    # --- Audio file download ---

    def download_audio_file(self, item_id, file_ino, dest_path):
        '''Download a specific audio file from an item.'''
        self._download(f'/api/items/{item_id}/file/{file_ino}', dest_path)

    # --- Metadata matching ---

    def match_item(self, item_id, provider='audible', title=None, author=None, isbn=None, asin=None):
        '''Search for metadata matches for an item.'''
        data = {'provider': provider}
        if title:
            data['title'] = title
        if author:
            data['author'] = author
        if isbn:
            data['isbn'] = isbn
        if asin:
            data['asin'] = asin
        return self._request('POST', f'/items/{item_id}/match',
                             data=json.dumps(data).encode())


def abs_item_to_calibre_metadata(item):
    '''
    Convert an Audiobookshelf library item to a Calibre Metadata object.

    :param item: dict from ABS API (expanded item)
    :return: Metadata object
    '''
    media = item.get('media', {})
    metadata = media.get('metadata', {})

    title = metadata.get('title', 'Unknown')
    authors = []
    for a in metadata.get('authors', []):
        if isinstance(a, dict):
            authors.append(a.get('name', ''))
        else:
            authors.append(str(a))

    mi = Metadata(title, authors or [_('Unknown')])

    # Series
    series_list = metadata.get('series', [])
    if series_list:
        s = series_list[0]
        if isinstance(s, dict):
            mi.series = s.get('name', '')
            seq = s.get('sequence', '')
            if seq:
                try:
                    mi.series_index = float(seq)
                except (ValueError, TypeError):
                    pass

    # Basic fields
    if metadata.get('publisher'):
        mi.publisher = metadata['publisher']
    if metadata.get('description'):
        mi.comments = metadata['description']
    if metadata.get('language'):
        mi.languages = [metadata['language']]
    if metadata.get('publishedYear'):
        from calibre.utils.date import parse_only_date
        try:
            mi.pubdate = parse_only_date(str(metadata['publishedYear']))
        except Exception:
            pass

    # Identifiers
    if metadata.get('isbn'):
        mi.isbn = metadata['isbn']
    if metadata.get('asin'):
        mi.set_identifier('asin', metadata['asin'])
    mi.set_identifier('audiobookshelf', item.get('id', ''))

    # Tags/genres
    tags = metadata.get('genres', []) or []
    tags.extend(media.get('tags', []) or [])
    if tags:
        mi.tags = list(set(tags))

    # Audiobook-specific
    narrators = metadata.get('narrators', [])
    if narrators:
        mi.narrator = ', '.join(
            n.get('name', n) if isinstance(n, dict) else str(n)
            for n in narrators
        )

    duration = media.get('duration', 0)
    if duration:
        mi.duration = float(duration)

    chapters = media.get('chapters', [])
    if chapters:
        mi.chapters = chapters

    return mi


def calibre_metadata_to_abs_match(mi):
    '''
    Convert Calibre Metadata to ABS match query parameters.

    :param mi: Calibre Metadata object
    :return: dict suitable for ABS match API
    '''
    result = {}
    if mi.title:
        result['title'] = mi.title
    if mi.authors:
        result['author'] = mi.authors[0]
    if mi.isbn:
        result['isbn'] = mi.isbn
    asin = mi.get_identifiers().get('asin')
    if asin:
        result['asin'] = asin
    return result
