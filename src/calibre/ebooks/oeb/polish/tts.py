#!/usr/bin/env python
# License: GPLv3 Copyright: 2024, Kovid Goyal <kovid at kovidgoyal.net>

import io
import json
import os
import sys
from collections import defaultdict
from contextlib import suppress
from functools import partial
from typing import NamedTuple

from lxml.etree import ElementBase as Element
from lxml.etree import tostring as _tostring

from calibre.ebooks.html_transform_rules import unwrap_tag
from calibre.ebooks.oeb.base import EPUB, EPUB_NS, SMIL_NS, barename
from calibre.ebooks.oeb.polish.container import OEB_DOCS, seconds_to_timestamp
from calibre.ebooks.oeb.polish.errors import UnsupportedContainerType
from calibre.ebooks.oeb.polish.upgrade import upgrade_book
from calibre.spell.break_iterator import sentence_positions
from calibre.utils.localization import canonicalize_lang, get_lang


class Sentence(NamedTuple):
    elem_id: str
    text: str
    lang: str
    voice: str


def tostring(x) -> str:
    return _tostring(x, encoding='unicode')


def lang_for_elem(elem, parent_lang):
    return canonicalize_lang(elem.get('lang') or elem.get('xml_lang') or elem.get('{http://www.w3.org/XML/1998/namespace}lang')) or parent_lang


def has_text(elem):
    if elem.text and elem.text.strip():
        return True
    for child in elem:
        if child.tail and child.tail.strip():
            return True
    return False


class Chunk(NamedTuple):
    child: Element | None
    text: str
    start_at: int
    is_tail: bool = False


continued_tag_names = frozenset({
    'a', 'span', 'em', 'strong', 'b', 'i', 'u', 'code', 'sub', 'sup', 'cite', 'q', 'kbd'
})
ignored_tag_names = frozenset({
    'img', 'object', 'script', 'style', 'head', 'title', 'form', 'input', 'br', 'hr', 'map', 'textarea', 'svg', 'math', 'rp', 'rt', 'rtc',
})
id_prefix = 'cttsw-'


def unmark_sentences_in_html(root):
    for x in root.xpath(f'//*[starts-with(@id, "{id_prefix}")]'):
        x.attrib.pop('id')
        if not x.attrib and x.tag and x.tag.endswith('span'):
            unwrap_tag(x)


def mark_sentences_in_html(root, lang: str = '', voice: str = '') -> list[Sentence]:
    root_lang = canonicalize_lang(lang_for_elem(root, canonicalize_lang(lang or get_lang())) or 'en')
    root_voice = voice
    seen_ids = set(root.xpath('//*/@id'))
    id_counter = 1
    ans = []
    clones_map = defaultdict(list)

    class Parent:

        def __init__(self, elem, tag_name, parent_lang, parent_voice, child_lang=''):
            self.elem = elem
            self.tag_name = tag_name
            self.lang = child_lang or lang_for_elem(elem, parent_lang)
            self.parent_lang = parent_lang
            q = elem.get('data-calibre-tts', '')
            self.voice = parent_voice
            if q.startswith('{'):  # }
                with suppress(Exception):
                    q = json.loads(q)
                    self.voice = q.get('voice') or parent_voice
            else:
                self.voice = q or parent_voice
            self.pos = 0
            self.texts = []
            if elem.text and elem.text.strip():
                self.texts.append(Chunk(None, elem.text, self.pos))
                self.pos += len(elem.text)
            self.children = tuple(elem.iterchildren())
            self.has_tail = bool((elem.tail or '').strip())

        def add_simple_child(self, elem):
            if text := elem.text:
                self.texts.append(Chunk(elem, text, self.pos))
                self.pos += len(text)

        def add_tail(self, elem, text):
            self.texts.append(Chunk(elem, text, self.pos, is_tail=True))
            self.pos += len(text)

        def commit(self) -> None:
            if self.texts:
                text = ''.join(c.text for c in self.texts)
                self.pos = 0
                for start, length in sentence_positions(text, self.lang):
                    elem_id = self.wrap_sentence(start, length)
                    ans.append(Sentence(elem_id, text[start:start+length], self.lang, self.voice))
            if self.has_tail:
                p = self.elem.getparent()
                spans = []
                before = after = None
                for start, length in sentence_positions(self.elem.tail, self.parent_lang):
                    end = start + length
                    text = self.elem.tail[start:end]
                    if before is None:
                        before = self.elem.tail[:start]
                    span = self.make_wrapper(text, p)
                    spans.append(span)
                    after = self.elem.tail[end:]
                self.elem.tail = before
                if after and spans:
                    spans[-1].tail = after
                idx = p.index(self.elem)
                p[idx+1:idx+1] = spans

        def make_into_wrapper(self, elem: Element) -> str:
            nonlocal id_counter
            while True:
                q = f'{id_prefix}{id_counter}'
                if q not in seen_ids:
                    elem.set('id', q)
                    seen_ids.add(q)
                    return q
                id_counter += 1

        def make_wrapper(self, text: str | None, elem: Element | None = None) -> Element:
            if elem is None:
                elem = self.elem
            ns, sep, _ = elem.tag.partition('}')
            ans = elem.makeelement(ns + sep + 'span')
            ans.text = text
            self.make_into_wrapper(ans)
            return ans

        def replace_reference_to_child(self, elem: Element, replacement: Element) -> None:
            for i in range(self.pos + 1, len(self.texts)):
                if self.texts[i].child is elem:
                    self.texts[i] = self.texts[i]._replace(child=replacement)
                else:
                    break

        def wrap_contents(self, first_child: Element | None, last_child: Element) -> Element:
            w = self.make_wrapper(self.elem.text if first_child is None else None)
            in_range = False
            for c in self.elem.iterchildren('*'):
                if not in_range and (first_child is None or first_child is c):
                    in_range = True
                    pos = self.elem.index(c)
                    self.elem.insert(pos, w)
                    w.append(c)
                    first_child = c
                if in_range:
                    if last_child is not first_child:
                        w.append(last_child)
                    if c is last_child:
                        break
            self.replace_reference_to_child(last_child, w)
            return w

        def clone_simple_element(self, elem: Element) -> Element:
            ans = elem.makeelement(elem.tag)
            ans.attrib.update(elem.attrib)
            ans.attrib.pop('id', None)
            ans.attrib.pop('name', None)
            ans.text, ans.tail = elem.text, elem.tail
            p = elem.getparent()
            idx = p.index(elem)
            p.insert(idx + 1, ans)
            self.replace_reference_to_child(elem, ans)
            clones_map[elem].append(ans)
            return ans

        def wrap_sentence(self, start: int, length: int) -> str:
            end = start + length
            start_chunk = end_chunk = -1
            start_offset = end_offset = 0
            for i in range(self.pos, len(self.texts)):
                c = self.texts[i]
                if c.start_at <= start:
                    start_chunk = i
                    start_offset = start - c.start_at
                if end <= c.start_at + len(c.text):
                    end_chunk = i
                    self.pos = i
                    end_offset = end - c.start_at
                    break
            else:
                self.pos = end_chunk = len(self.texts) - 1
                end_offset = len(self.texts[-1].text)
            assert start_chunk > -1
            s, e = self.texts[start_chunk], self.texts[end_chunk]
            if s.child is None: # start in leading text of parent element
                if e is s:  # end also in leading text of parent element
                    before, sentence, after = s.text[:start_offset], s.text[start_offset:end_offset], s.text[end_offset:]
                    self.elem.text = before
                    w = self.make_wrapper(sentence)
                    self.elem.insert(0, w)
                    w.tail = after
                    if after:
                        self.texts[self.pos] = Chunk(w, after, end, is_tail=True)
                    else:
                        self.pos += 1
                    return w.get('id')
                if e.is_tail:  # ending in the tail of a child
                    before_start, after_start = s.text[:start_offset], s.text[start_offset:]
                    included, after = e.text[:end_offset], e.text[end_offset:]
                    e.child.tail = included
                    self.elem.text = after_start
                    w = self.wrap_contents(None, e.child)
                    w.tail = after
                    self.elem.text = before_start
                    if after:
                        self.texts[self.pos] = Chunk(w, after, end, is_tail=True)
                    else:
                        self.pos += 1
                    return w.get('id')
                # ending inside a child
                before_start, after_start = s.text[:start_offset], s.text[start_offset:]
                included, after = e.text[:end_offset], e.text[end_offset:]
                e.child.text = included
                c = self.clone_simple_element(e.child)
                c.text = after
                e.child.tail = None
                self.elem.text = after_start
                w = self.wrap_contents(None, e.child)
                self.elem.text = before_start
                if after:
                    self.texts[self.pos] = Chunk(c, c.text, end)
                else:
                    self.pos += 1
                return w.get('id')
            # starting in a child text or tail
            if s.is_tail:
                if e.is_tail:
                    if s is e:  # end in tail of same element
                        before, sentence, after = s.text[:start_offset], s.text[start_offset:end_offset], s.text[end_offset:]
                        s.child.tail = before
                        w = self.make_wrapper(sentence)
                        w.tail = after
                        idx = self.elem.index(s.child)
                        self.elem.insert(idx + 1, w)
                        if after:
                            self.texts[self.pos] = Chunk(w, after, end, is_tail=True)
                        else:
                            self.pos += 1
                        return w.get('id')
                    s.child.tail, after_start = s.text[:start_offset], s.text[start_offset:]
                    e.child.tail, after_end = e.text[:end_offset], e.text[end_offset:]
                    idx = self.elem.index(s.child)
                    w = self.wrap_contents(self.elem[idx+1], e.child)
                    w.text, w.tail = after_start, after_end
                    if after_end:
                        self.texts[self.pos] = Chunk(w, after_end, end, is_tail=True)
                    else:
                        self.pos += 1
                    return w.get('id')
                # end inside some subsequent simple element
                s.child.tail, after_start = s.text[:start_offset], s.text[start_offset:]
                e.child.text, after_end = e.text[:end_offset], e.text[end_offset:]
                c = self.clone_simple_element(e.child)
                c.text = after_end
                e.child.tail = None
                w = self.wrap_contents(self.elem[self.elem.index(s.child) + 1], e.child)
                w.text = after_start
                if after_end:
                    self.texts[self.pos] = Chunk(c, after_end, end)
                else:
                    self.pos += 1
                return w.get('id')
            # start is in the text of a simple child
            if s.child is e.child:
                if e.is_tail:  # ending in tail of element we start in
                    before_start, after_start = s.text[:start_offset], s.text[start_offset:]
                    c = self.clone_simple_element(s.child)
                    s.child.text, s.child.tail = before_start, None
                    before_end, after_end = e.text[:end_offset], e.text[end_offset:]
                    c.text, c.tail = after_start, before_end
                    w = self.wrap_contents(c, c)
                    w.tail = after_end
                    if after_end:
                        self.texts[self.pos] = Chunk(w, after_end, end, is_tail=True)
                    else:
                        self.pos += 1
                    return w.get('id')
                # start and end in text of element
                before, sentence, after = s.text[:start_offset], s.text[start_offset:end_offset], s.text[end_offset:]
                c = self.clone_simple_element(s.child)
                s.child.text, s.child.tail = before, None
                c.text, c.tail = sentence, None
                c2 = self.clone_simple_element(c)
                c2.text = after
                self.make_into_wrapper(c)
                if after:
                    self.texts[self.pos] = Chunk(c2, after, end)
                else:
                    self.pos += 1
                return c.get('id')
            # end is in a subsequent simple child or tail of one
            s.child.text, after_start = s.text[:start_offset], s.text[start_offset:]
            c = self.clone_simple_element(s.child)
            c.text, s.child.tail = after_start, None
            if e.is_tail:
                e.child.tail, after_end = e.text[:end_offset], e.text[end_offset:]
                w = self.wrap_contents(c, e.child)
                w.tail = after_end
                if after_end:
                    self.texts[self.pos] = Chunk(w, after_end, end, is_tail=True)
                else:
                    self.pos += 1
                return w.get('id')
            # end is in text of subsequent simple child
            e.child.text, after_end = e.text[:end_offset], e.text[end_offset:]
            c2 = self.clone_simple_element(e.child)
            c2.text, e.child.tail = after_end, None
            w = self.wrap_contents(c, e.child)
            if after_end:
                self.texts[self.pos] = Chunk(c2, after_end, end)
            else:
                self.pos += 1
            return w.get('id')

    stack_of_parents = [Parent(elem, 'body', root_lang, root_voice) for elem in root.iterchildren('*') if barename(elem.tag).lower() == 'body']
    while stack_of_parents:
        p = stack_of_parents.pop()
        simple_allowed = True
        children_to_process = []
        for child in p.children:
            child_voice = child.get('data-calibre-tts', '')
            child_lang = lang_for_elem(child, p.lang)
            child_tag_name = barename(child.tag).lower() if isinstance(child.tag, str) else ''
            if simple_allowed and child_lang == p.lang and child_voice == p.voice and child_tag_name in continued_tag_names and len(child) == 0:
                p.add_simple_child(child)
            elif child_tag_name not in ignored_tag_names:
                simple_allowed = False
                children_to_process.append(Parent(child, child_tag_name, p.lang, p.voice, child_lang=child_lang))
            if simple_allowed and (text := child.tail):
                p.add_tail(child, text)
        p.commit()
        stack_of_parents.extend(reversed(children_to_process))
    for src_elem, clones in clones_map.items():
        for clone in clones + [src_elem]:
            if not clone.text and not clone.tail and not clone.get('id') and not clone.get('name'):
                if (p := clone.getparent()) is not None:
                    p.remove(clone)
    return ans


class PerFileData:

    def __init__(self, name: str):
        self.name = name
        self.root = None
        self.sentences: list[Sentence] = []
        self.key_map: dict[tuple[str, str], list[Sentence]] = defaultdict(list)
        self.audio_file_name = self.smil_file_name = ''


class ReportProgress:

    def __init__(self):
        self.current_stage = ''

    def __call__(self, stage: str, item: str, count: int, total: int) -> bool:
        if stage != self.current_stage:
            self.current_stage = stage
            print()
            print(self.current_stage)
            return False
        frac = count / total
        print(f'\r{frac:4.0%} {item}', end='')
        return False


def make_par(container, seq, html_href, audio_href, elem_id, pos, duration) -> None:
    seq.set(EPUB('textref'), html_href)
    par = seq.makeelement('par')
    par.tail = seq.text
    par.set('id', f'par-{len(seq) + 1}')
    seq.append(par)
    par.text = seq.text + '  '
    text = par.makeelement('text')
    text.set('src', f'{html_href}#{elem_id}')
    text.tail = par.text
    par.append(text)
    audio = par.makeelement('audio')
    audio.tail = par.tail
    par.append(audio)
    audio.set('src', audio_href)
    audio.set('clipBegin', seconds_to_timestamp(pos))
    audio.set('clipEnd', seconds_to_timestamp(pos + duration))


def remove_embedded_tts(container):
    manifest_items = container.manifest_items
    id_map = {item.get('id'): item for item in manifest_items}
    container.set_media_overlay_durations({})
    media_files = set()
    for item in manifest_items:
        smil_id = item.get('media-overlay')
        href = item.get('href')
        if href and smil_id:
            name = container.href_to_name(href, container.opf_name)
            root = container.parsed(name)
            unmark_sentences_in_html(root)
            container.dirty(name)
            smil_item = id_map.get(smil_id)
            if smil_item:
                smil_href = smil_item.get('href')
                if smil_href:
                    smil_name = container.href_to_name(smil_item.get('href'))
                    smil_root = container.parsed(smil_name)
                    for ahref in smil_root.xpath('//@src'):
                        aname = container.href_to_name(ahref, smil_name)
                        media_files.add(aname)
                    container.remove_from_xml(smil_item)
    for aname in media_files:
        container.remove_item(aname)


def embed_tts(container, report_progress=None, callback_to_download_voices=None):
    report_progress = report_progress or ReportProgress()
    if container.book_type != 'epub':
        raise UnsupportedContainerType(_('Only the EPUB format has support for embedding speech overlay audio'))
    if container.opf_version_parsed[0] < 3:
        if report_progress(_('Updating book internals'), '', 0, 0):
            return False
        upgrade_book(container, print)
    remove_embedded_tts(container)

    from calibre.gui2.tts.piper import HIGH_QUALITY_SAMPLE_RATE, PiperEmbedded
    from calibre_extensions.ffmpeg import transcode_single_audio_stream, wav_header_for_pcm_data

    piper = PiperEmbedded()
    language = container.mi.language
    name_map = {}
    for name, is_linear in container.spine_names:
        if container.mime_map.get(name) in OEB_DOCS:
            name_map[name] = PerFileData(name)
    stage = _('Processing HTML')
    if report_progress(stage, '', 0, len(name_map)):
        return False
    all_voices = set()
    total_num_sentences = 0
    for i, (name, pfd) in enumerate(name_map.items()):
        pfd.root = container.parsed(name)
        pfd.sentences = mark_sentences_in_html(pfd.root, lang=language)
        total_num_sentences += len(pfd.sentences)
        for s in pfd.sentences:
            key = s.lang, s.voice
            pfd.key_map[key].append(s)
            all_voices.add(key)
        container.dirty(name)
        if report_progress(stage, name, i+1, len(name_map)):
            return False
    if callback_to_download_voices is None:
        piper.ensure_voices_downloaded(iter(all_voices))
    else:
        if not callback_to_download_voices(partial(piper.ensure_voices_downloaded, iter(all_voices))):
            return False
    stage = _('Converting text to speech')
    if report_progress(stage, '', 0, total_num_sentences):
        return False
    snum = 0
    size_of_audio_data = 0
    mmap = {container.href_to_name(item.get('href'), container.opf_name):item for item in container.manifest_items}
    duration_map = {}
    for name, pfd in name_map.items():
        audio_map: dict[Sentence, tuple[bytes, float]] = {}
        for (lang, voice), sentences in pfd.key_map.items():
            texts = tuple(s.text for s in sentences)
            for i, (audio_data, duration) in enumerate(piper.text_to_raw_audio_data(texts, lang, voice, sample_rate=HIGH_QUALITY_SAMPLE_RATE)):
                s = sentences[i]
                audio_map[s] = audio_data, duration
                size_of_audio_data += len(audio_data)
                snum += 1
                if report_progress(stage, _('Sentence: {0} of {1}').format(snum, total_num_sentences), snum, total_num_sentences):
                    return False
        wav = io.BytesIO()
        wav.write(wav_header_for_pcm_data(size_of_audio_data, HIGH_QUALITY_SAMPLE_RATE))
        afitem = container.generate_item(name + '.m4a', id_prefix='tts-')
        pfd.audio_file_name = container.href_to_name(afitem.get('href'), container.opf_name)
        smilitem = container.generate_item(name + '.smil', id_prefix='smil-')
        pfd.smil_file_name = container.href_to_name(smilitem.get('href'), container.opf_name)
        with container.open(pfd.smil_file_name, 'w') as sf:
            sf.write(f'''\
<smil xmlns="{SMIL_NS}" xmlns:epub="{EPUB_NS}" version="3.0">
  <body>
    <seq id="generated-by-calibre">
      X
    </seq>
  </body>
</smil>''')
        smil_root = container.parsed(pfd.smil_file_name)
        seq = smil_root[0][0]
        seq.text = seq.text[:seq.text.find('X')]
        audio_href = container.name_to_href(pfd.audio_file_name, pfd.smil_file_name)
        html_href = container.name_to_href(pfd.name, pfd.smil_file_name)
        file_duration = 0
        for i, s in enumerate(pfd.sentences):
            audio_data, duration = audio_map[s]
            wav.write(audio_data)
            make_par(container, seq, html_href, audio_href, s.elem_id, file_duration, duration)
            file_duration += duration
        if len(seq):
            seq[-1].tail = seq.text[:-2]
        wav.seek(0)
        with container.open(pfd.audio_file_name, 'wb') as m4a:
            transcode_single_audio_stream(wav, m4a)
        container.pretty_print.add(pfd.smil_file_name)
        container.dirty(pfd.smil_file_name)
        container.serialize_item(pfd.smil_file_name)
        html_item = mmap[name]
        html_item.set('media-overlay', smilitem.get('id'))
        duration_map[smilitem.get('id')] = file_duration
    container.set_media_overlay_durations(duration_map)


def develop():
    from calibre.ebooks.oeb.polish.container import get_container
    path = sys.argv[-1]
    container = get_container(path, tweak_mode=True)
    embed_tts(container)
    b, e = os.path.splitext(path)
    outpath = b + '-tts' + e
    container.commit(outpath)
    print('Output saved to:', outpath)


if __name__ == '__main__':
    develop()
