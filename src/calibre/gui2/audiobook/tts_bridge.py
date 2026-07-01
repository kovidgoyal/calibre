#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Calibre Contributors

'''
Bridge between ebooks and audiobooks:
- Ebook → Audiobook: TTS synthesis using Calibre's built-in Piper engine
- Audiobook → Ebook transcript: Speech-to-text (placeholder for Whisper integration)
- Chapter alignment between audio and text positions
'''

import os
import re
import tempfile

from calibre.ebooks.metadata.book.base import Metadata


def ebook_to_audiobook(input_path, output_dir, language='en', report_progress=None):
    '''
    Convert an ebook to a set of MP3 audiobook files using Piper TTS.

    :param input_path: Path to the ebook file (EPUB, PDF, etc.)
    :param output_dir: Directory to write MP3 chapter files
    :param language: Language code for TTS voice selection
    :param report_progress: Optional callback(stage, detail, current, total)
    :return: dict with {chapters: [{title, path, duration}], total_duration, language}
    '''
    from calibre.gui2.tts.piper import HIGH_QUALITY_SAMPLE_RATE, PiperEmbedded

    if report_progress is None:
        report_progress = lambda *a: False

    # Step 1: Extract text from ebook
    if report_progress('Extracting text', input_path, 0, 3):
        return None
    text = _extract_text_from_ebook(input_path)
    if not text:
        raise ValueError(f'Could not extract text from {input_path}')

    # Step 2: Split into chapters
    chapters = _split_into_chapters(text)
    if report_progress('Splitting chapters', f'{len(chapters)} chapters found', 1, 3):
        return None

    os.makedirs(output_dir, exist_ok=True)

    # Step 3: Generate TTS audio per chapter
    piper = PiperEmbedded()
    voice_key = (language, '')
    piper.ensure_voices_downloaded(iter([voice_key]))

    result_chapters = []
    total_duration = 0.0

    for i, (title, chapter_text) in enumerate(chapters):
        if report_progress('Generating audio', f'Chapter {i+1}/{len(chapters)}: {title}', i, len(chapters)):
            return None

        if not chapter_text.strip():
            continue

        # Generate raw audio via Piper
        sentences = _split_sentences(chapter_text)
        raw_audio = b''
        for audio_data, duration in piper.text_to_raw_audio_data(
            tuple(sentences), language, '', sample_rate=HIGH_QUALITY_SAMPLE_RATE
        ):
            raw_audio += audio_data

        if not raw_audio:
            continue

        # Convert raw PCM to MP3 via ffmpeg extension
        from calibre_extensions.ffmpeg import wav_header_for_pcm_data, transcode_single_audio_stream
        import io

        wav_buf = io.BytesIO()
        wav_buf.write(wav_header_for_pcm_data(len(raw_audio), HIGH_QUALITY_SAMPLE_RATE))
        wav_buf.write(raw_audio)
        wav_buf.seek(0)

        safe_title = re.sub(r'[^\w\s-]', '', title)[:50].strip()
        mp3_filename = f'{i+1:03d} - {safe_title}.mp3'
        mp3_path = os.path.join(output_dir, mp3_filename)

        with open(mp3_path, 'wb') as mp3_file:
            transcode_single_audio_stream(wav_buf, mp3_file)

        chapter_duration = len(raw_audio) / (HIGH_QUALITY_SAMPLE_RATE * 2)  # 16-bit mono
        result_chapters.append({
            'title': title,
            'path': mp3_path,
            'duration': chapter_duration,
            'start': total_duration,
        })
        total_duration += chapter_duration

    return {
        'chapters': result_chapters,
        'total_duration': total_duration,
        'language': language,
    }


def _extract_text_from_ebook(path):
    '''Extract plain text from an ebook using Calibre's conversion pipeline.'''
    from calibre.ebooks.oeb.polish.container import get_container
    from calibre.ebooks.oeb.base import xml2text

    ext = os.path.splitext(path)[1].lower().lstrip('.')
    try:
        container = get_container(path)
    except Exception:
        # Fallback: use ebook-convert to txt
        return _convert_to_text_fallback(path)

    texts = []
    for name, is_linear in container.spine_names:
        if container.mime_map.get(name, '').startswith(('application/xhtml', 'text/html')):
            try:
                root = container.parsed(name)
                texts.append(xml2text(root))
            except Exception:
                continue
    return '\n\n'.join(texts)


def _convert_to_text_fallback(path):
    '''Fallback: convert ebook to text via subprocess.'''
    import subprocess
    with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as tmp:
        tmp_path = tmp.name
    try:
        from calibre.utils.resources import get_path as calibre_path
        convert_cmd = 'ebook-convert'
        subprocess.run([convert_cmd, path, tmp_path], capture_output=True, timeout=120)
        with open(tmp_path, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()
    except Exception:
        return ''
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def _split_into_chapters(text):
    '''Split text into chapters based on common chapter markers.'''
    chapter_pattern = re.compile(
        r'^(?:chapter|part|section|book)\s+[\divxlc]+[.:\s]*(.*)',
        re.IGNORECASE | re.MULTILINE
    )

    matches = list(chapter_pattern.finditer(text))
    if not matches:
        # No chapter markers found — split into ~5000 char chunks
        chunks = []
        for i in range(0, len(text), 5000):
            chunk = text[i:i+5000]
            title = f'Part {len(chunks) + 1}'
            chunks.append((title, chunk))
        return chunks if chunks else [('Full Text', text)]

    chapters = []
    for i, match in enumerate(matches):
        title = match.group(1).strip() or f'Chapter {i + 1}'
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        chapters.append((title, text[start:end]))

    # Include any text before the first chapter marker
    if matches[0].start() > 100:
        chapters.insert(0, ('Preface', text[:matches[0].start()]))

    return chapters


def _split_sentences(text, max_length=500):
    '''Split text into sentences suitable for TTS.'''
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    result = []
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        if len(s) > max_length:
            # Split long sentences at commas or mid-point
            parts = s.split(', ')
            for p in parts:
                if p.strip():
                    result.append(p.strip())
        else:
            result.append(s)
    return result


def get_chapter_alignment(audio_chapters, ebook_toc):
    '''
    Align audiobook chapters with ebook TOC entries by title similarity.

    :param audio_chapters: list of {title, start, end, duration}
    :param ebook_toc: list of {title, href/cfi}
    :return: list of {audio_chapter, ebook_entry, confidence}
    '''
    alignments = []
    for ach in audio_chapters:
        best_match = None
        best_score = 0
        a_title = _normalize_title(ach.get('title', ''))
        for entry in ebook_toc:
            e_title = _normalize_title(entry.get('title', ''))
            score = _title_similarity(a_title, e_title)
            if score > best_score:
                best_score = score
                best_match = entry
        if best_match and best_score > 0.3:
            alignments.append({
                'audio_chapter': ach,
                'ebook_entry': best_match,
                'confidence': best_score,
            })
    return alignments


def _normalize_title(title):
    '''Normalize a chapter title for comparison.'''
    title = title.lower().strip()
    title = re.sub(r'^(chapter|part|section)\s+', '', title)
    title = re.sub(r'[\d\s:.\-–—]+', ' ', title)
    return title.strip()


def _title_similarity(a, b):
    '''Simple word-overlap similarity between two titles.'''
    if not a or not b:
        return 0.0
    words_a = set(a.split())
    words_b = set(b.split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    return len(intersection) / max(len(words_a), len(words_b))
