#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Calibre Contributors

'''
Read metadata from audio book files (M4B, MP3, M4A, FLAC, OGG, OPUS).
Uses ffprobe (via subprocess) or mutagen-style tag reading via calibre's
built-in ffmpeg extension for probing.
'''

import json
import os
import re
import struct
import subprocess

from calibre.ebooks.metadata.book.base import Metadata

AUDIO_EXTENSIONS = frozenset({
    'm4b', 'mp3', 'm4a', 'flac', 'ogg', 'opus', 'oga',
    'mp4', 'aac', 'wma', 'aiff', 'wav', 'webm', 'mka',
})

AUDIO_MIME_TYPES = {
    'mp3': 'audio/mpeg',
    'm4b': 'audio/mp4',
    'm4a': 'audio/mp4',
    'mp4': 'audio/mp4',
    'flac': 'audio/flac',
    'ogg': 'audio/ogg',
    'oga': 'audio/ogg',
    'opus': 'audio/ogg',
    'aac': 'audio/aac',
    'wma': 'audio/x-ms-wma',
    'aiff': 'audio/x-aiff',
    'wav': 'audio/wav',
    'webm': 'audio/webm',
    'mka': 'audio/x-matroska',
}


def _find_ffprobe():
    '''Find ffprobe binary on the system.'''
    for name in ('ffprobe', 'ffprobe.exe'):
        for d in os.environ.get('PATH', '').split(os.pathsep):
            p = os.path.join(d, name)
            if os.path.isfile(p) and os.access(p, os.X_OK):
                return p
    return None


def probe_audio_file(path):
    '''
    Probe an audio file using ffprobe and return a dict with:
    - format: container format name
    - duration: float seconds
    - bit_rate: int bits/sec
    - tags: dict of metadata tags (lowercased keys)
    - chapters: list of {id, start, end, title}
    - streams: list of stream info dicts
    '''
    ffprobe = _find_ffprobe()
    if ffprobe is None:
        raise FileNotFoundError('ffprobe not found in PATH. Install ffmpeg to read audio metadata.')

    cmd = [
        ffprobe, '-v', 'quiet',
        '-print_format', 'json',
        '-show_format', '-show_chapters', '-show_streams',
        path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f'ffprobe failed for {path}: {result.stderr[:500]}')

    return json.loads(result.stdout)


def _parse_chapters(probe_data):
    '''Extract chapter list from ffprobe data.'''
    chapters = []
    for ch in probe_data.get('chapters', []):
        time_base_num, time_base_den = 1, 1
        tb = ch.get('time_base', '1/1')
        if '/' in tb:
            parts = tb.split('/')
            time_base_num, time_base_den = int(parts[0]), int(parts[1])

        start = float(ch.get('start_time', 0))
        end = float(ch.get('end_time', 0))
        title = ch.get('tags', {}).get('title', f'Chapter {ch.get("id", len(chapters) + 1)}')
        chapters.append({
            'id': ch.get('id', len(chapters)),
            'start': start,
            'end': end,
            'title': title,
        })
    return sorted(chapters, key=lambda c: c['start'])


def _get_cover_data(probe_data, path):
    '''Extract embedded cover art from audio file.'''
    for stream in probe_data.get('streams', []):
        if stream.get('codec_type') == 'video' and stream.get('disposition', {}).get('attached_pic', 0):
            ffprobe = _find_ffprobe()
            if not ffprobe:
                return None
            ffmpeg = ffprobe.replace('ffprobe', 'ffmpeg')
            if not os.path.isfile(ffmpeg):
                return None
            try:
                result = subprocess.run(
                    [ffmpeg, '-v', 'quiet', '-i', path, '-an', '-vcodec', 'copy', '-f', 'image2pipe', '-'],
                    capture_output=True, timeout=15
                )
                if result.returncode == 0 and result.stdout:
                    # Detect image format from magic bytes
                    data = result.stdout
                    if data[:3] == b'\xff\xd8\xff':
                        return ('jpeg', data)
                    elif data[:8] == b'\x89PNG\r\n\x1a\n':
                        return ('png', data)
                    return ('jpeg', data)
            except Exception:
                pass
    return None


def get_metadata(stream_or_path, ftype='m4b'):
    '''
    Read metadata from an audio file.

    :param stream_or_path: file path string or file-like object
    :param ftype: file extension (m4b, mp3, etc.)
    :return: Metadata object
    '''
    if hasattr(stream_or_path, 'name'):
        path = stream_or_path.name
    elif hasattr(stream_or_path, 'read'):
        # Write to temp file for ffprobe
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=f'.{ftype}', delete=False) as tmp:
            tmp.write(stream_or_path.read())
            path = tmp.name
    else:
        path = stream_or_path

    try:
        probe_data = probe_audio_file(path)
    except (FileNotFoundError, RuntimeError):
        # Fallback: return minimal metadata from filename
        mi = Metadata(os.path.splitext(os.path.basename(path))[0])
        return mi

    fmt = probe_data.get('format', {})
    tags = {k.lower(): v for k, v in fmt.get('tags', {}).items()}

    # Title
    title = tags.get('title') or tags.get('album') or os.path.splitext(os.path.basename(path))[0]
    mi = Metadata(title)

    # Authors (artist, author, albumartist)
    author = tags.get('author') or tags.get('artist') or tags.get('albumartist') or tags.get('album_artist')
    if author:
        mi.authors = [a.strip() for a in re.split(r'[,;&/]', author)]

    # Narrator (composer field is commonly used for narrator)
    narrator = tags.get('composer') or tags.get('narrator') or tags.get('performed_by')
    if narrator:
        mi.narrator = narrator

    # Series
    series = tags.get('series') or tags.get('mvnm') or tags.get('grouping')
    if series:
        mi.series = series
        series_index = tags.get('series-part') or tags.get('mvn') or tags.get('track')
        if series_index:
            try:
                mi.series_index = float(re.sub(r'[^\d.]', '', str(series_index)))
            except (ValueError, TypeError):
                pass

    # Publisher
    publisher = tags.get('publisher') or tags.get('label')
    if publisher:
        mi.publisher = publisher

    # Description/comments
    desc = tags.get('description') or tags.get('comment') or tags.get('synopsis')
    if desc:
        mi.comments = desc

    # Language
    lang = tags.get('language')
    if lang:
        mi.languages = [lang]

    # Date
    date_str = tags.get('date') or tags.get('year')
    if date_str:
        from calibre.utils.date import parse_only_date
        try:
            mi.pubdate = parse_only_date(date_str[:10])
        except Exception:
            pass

    # ISBN / ASIN
    isbn = tags.get('isbn')
    if isbn:
        mi.isbn = isbn
    asin = tags.get('asin')
    if asin:
        mi.set_identifier('asin', asin)

    # Genre → tags
    genre = tags.get('genre')
    if genre:
        mi.tags = [g.strip() for g in re.split(r'[,;/]', genre)]

    # Duration (seconds)
    duration = float(fmt.get('duration', 0))
    if duration > 0:
        mi.duration = duration

    # Chapters
    chapters = _parse_chapters(probe_data)
    if chapters:
        mi.chapters = chapters

    # Cover art
    cover = _get_cover_data(probe_data, path)
    if cover:
        mi.cover_data = cover

    # Audio-specific metadata
    for s in probe_data.get('streams', []):
        if s.get('codec_type') == 'audio':
            mi.audio_codec = s.get('codec_name', '')
            mi.audio_channels = s.get('channels', 0)
            mi.audio_sample_rate = int(s.get('sample_rate', 0))
            mi.audio_bitrate = int(fmt.get('bit_rate', 0))
            break

    return mi
