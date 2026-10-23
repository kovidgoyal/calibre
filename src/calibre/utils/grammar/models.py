#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

# Metadata about, and management of, the neural network models used for
# grammar checking and sentence improvement suggestions. The models are
# downloaded on demand into the calibre cache directory.

import hashlib
import json
import os
import shutil
from collections.abc import Callable, Iterator
from contextlib import suppress
from functools import lru_cache
from threading import Event
from typing import Literal, NamedTuple, Protocol, TypedDict

Variant = Literal['cpu', 'gpu']
Task = Literal['check', 'suggest']
FileRole = Literal['encoder', 'decoder', 'decoder_with_past', 'tokenizer']
FILE_ROLES: tuple[FileRole, ...] = ('encoder', 'decoder', 'decoder_with_past', 'tokenizer')
# Prompt keys that are not suggestion kinds
NON_SUGGESTION_PROMPTS = frozenset({'check'})
DOWNLOAD_CHUNK_SIZE = 1024 * 1024


class FileData(TypedDict):
    url: str
    sha256: str
    size: int


class VariantFiles(TypedDict):
    encoder: FileData
    decoder: FileData
    decoder_with_past: FileData | None
    tokenizer: FileData


class ModelData(TypedDict):
    name: str
    description: str
    source: str
    license: str
    attribution: str
    languages: list[str]  # ISO 639-1 codes
    # Maps the task (check) or suggestion kind (grammar, fluency, etc.) to the
    # text prepended to the sentence to tell the model what to do
    prompts: dict[str, str]
    max_length: int
    auto_gpu: bool  # whether to use the GPU variant when the GPU setting is auto
    decoder_start_token_id: int
    eos_token_id: int
    pad_token_id: int
    variants: dict[str, VariantFiles]


class GrammarMetadata(TypedDict):
    version: int
    defaults: dict[str, dict[str, str]]  # task -> language -> model id
    models: dict[str, ModelData]


class ModelFiles(NamedTuple):
    encoder: str
    decoder: str
    decoder_with_past: str | None
    tokenizer: str


class Readable(Protocol):
    def read(self, size: int = -1, /) -> bytes: ...


class DownloadAborted(Exception):
    pass


class DownloadCorrupted(ValueError):
    pass


@lru_cache(2)
def grammar_metadata() -> GrammarMetadata:
    from calibre.utils.resources import get_path as P

    ans: GrammarMetadata = json.loads(P('grammar-models.json', data=True))
    return ans


def model_data(model_id: str) -> ModelData:
    try:
        return grammar_metadata()['models'][model_id]
    except KeyError:
        raise KeyError(f'Unknown grammar model: {model_id}') from None


def canonical_lang(lang: str | None) -> str:
    """Convert a language code such as en_US, en-GB or eng to a two letter ISO 639-1 code, defaulting to English"""
    if not lang:
        return 'en'
    lang = lang.replace('-', '_').partition('_')[0].lower()
    if len(lang) == 3:
        from calibre.utils.localization import lang_as_iso639_1

        lang = lang_as_iso639_1(lang) or lang
    return lang


def default_model(task: Task, lang: str | None = None) -> str | None:
    """Return the id of the default model for the specified task and language or None if the language is not supported"""
    return grammar_metadata()['defaults'].get(task, {}).get(canonical_lang(lang))


def models_for(task: Task, lang: str | None = None) -> list[str]:
    """Return the ids of all models supporting the specified task and language, with the default model first"""
    lang = canonical_lang(lang)
    ans = []
    for model_id, md in grammar_metadata()['models'].items():
        if lang in md['languages'] and supports_task(md, task):
            ans.append(model_id)
    d = default_model(task, lang)
    ans.sort(key=lambda x: x != d)
    return ans


def supports_task(md: ModelData, task: Task) -> bool:
    if task == 'check':
        return 'check' in md['prompts']
    return bool(set(md['prompts']) - NON_SUGGESTION_PROMPTS)


def suggestion_kinds(model_id: str) -> tuple[str, ...]:
    return tuple(k for k in model_data(model_id)['prompts'] if k not in NON_SUGGESTION_PROMPTS)


def available_variants(model_id: str) -> tuple[Variant, ...]:
    v = model_data(model_id)['variants']
    ans: list[Variant] = []
    if 'cpu' in v:
        ans.append('cpu')
    if 'gpu' in v:
        ans.append('gpu')
    return tuple(ans)


def models_dir() -> str:
    from calibre.constants import cache_dir

    return os.path.join(cache_dir(), 'grammar', 'models')


def file_path(model_id: str, fd: FileData) -> str:
    # The hash is part of the name so that changed files are downloaded again
    # and files shared by variants are downloaded only once
    name = fd['url'].rpartition('/')[-1]
    return os.path.join(models_dir(), model_id, f'{fd["sha256"][:16]}-{name}')


def variant_files(model_id: str, variant: Variant) -> VariantFiles:
    try:
        return model_data(model_id)['variants'][variant]
    except KeyError:
        raise KeyError(f'The grammar model {model_id} has no {variant} variant') from None


def iter_files(model_id: str, variant: Variant) -> Iterator[tuple[FileRole, FileData, str]]:
    vf = variant_files(model_id, variant)
    for role in FILE_ROLES:
        if (fd := vf[role]) is not None:
            yield role, fd, file_path(model_id, fd)


def model_files(model_id: str, variant: Variant) -> ModelFiles:
    paths: dict[FileRole, str] = {role: path for role, fd, path in iter_files(model_id, variant)}
    return ModelFiles(paths['encoder'], paths['decoder'], paths.get('decoder_with_past'), paths['tokenizer'])


def is_file_present(fd: FileData, path: str) -> bool:
    try:
        return os.path.getsize(path) == fd['size']
    except OSError:
        return False


def is_downloaded(model_id: str, variant: Variant) -> bool:
    return all(is_file_present(fd, path) for role, fd, path in iter_files(model_id, variant))


def download_size(model_id: str, variant: Variant) -> int:
    """The number of bytes that need to be downloaded for the specified model variant"""
    return sum(fd['size'] for role, fd, path in iter_files(model_id, variant) if not is_file_present(fd, path))


def file_description(role: FileRole) -> str:
    from calibre.utils.localization import _

    if role == 'tokenizer':
        return _('Vocabulary')
    return _('Neural network data')


def files_to_download(model_id: str, variant: Variant) -> tuple[dict[str, tuple[str, str]], dict[str, str]]:
    """
    Return (urls, hashes) for the files of the model variant that are not
    already downloaded, suitable for use with calibre.gui2.tts.download.download_resources().
    The directories for the files are created.
    """
    urls: dict[str, tuple[str, str]] = {}
    hashes: dict[str, str] = {}
    for role, fd, path in iter_files(model_id, variant):
        if not is_file_present(fd, path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            urls[fd['url']] = path, file_description(role)
            hashes[fd['url']] = fd['sha256']
    return urls, hashes


def download_file(
    fd: FileData, path: str, progress: Callable[[int], None] | None = None, abort: Event | None = None, opener: Callable[[str], Readable] | None = None
) -> None:
    """
    Download the file to path, verifying its hash. The data is first written
    to a temporary file and only moved to path if it is valid. progress is
    called with the number of bytes received so far.
    """
    if opener is None:
        from calibre import browser

        br = browser()
        opener = br.open_novisit
    os.makedirs(os.path.dirname(path), exist_ok=True)
    part_path = path + '.part'
    h = hashlib.sha256()
    received = 0
    try:
        res = opener(fd['url'])
        with open(part_path, 'wb') as f:
            while True:
                if abort is not None and abort.is_set():
                    raise DownloadAborted(f'Download of {fd["url"]} was aborted')
                chunk = res.read(DOWNLOAD_CHUNK_SIZE)
                if not chunk:
                    break
                h.update(chunk)
                f.write(chunk)
                received += len(chunk)
                if progress is not None:
                    progress(received)
        if received != fd['size'] or h.hexdigest() != fd['sha256'].lower():
            raise DownloadCorrupted(f'The data downloaded from {fd["url"]} is corrupted, its size or checksum does not match')
        os.replace(part_path, path)
    except BaseException:
        with suppress(OSError):
            os.remove(part_path)
        raise


def download_model(model_id: str, variant: Variant, progress: Callable[[int, int], None] | None = None, abort: Event | None = None) -> None:
    """
    Download the files of the specified model variant that are not already
    present, without any GUI. progress is called with (bytes received, total
    bytes to download). Raises an exception on failure.
    """
    needed = [(fd, path) for role, fd, path in iter_files(model_id, variant) if not is_file_present(fd, path)]
    total = sum(fd['size'] for fd, path in needed)
    done = 0
    for fd, path in needed:

        def file_progress(received: int, base: int = done) -> None:
            if progress is not None:
                progress(base + received, total)

        download_file(fd, path, file_progress, abort)
        done += fd['size']


def delete_model(model_id: str, variant: Variant | None = None) -> None:
    """Delete the downloaded files for the model variant, or all variants if variant is None. Files shared with other variants are kept."""
    if variant is None:
        with suppress(FileNotFoundError):
            shutil.rmtree(os.path.join(models_dir(), model_id))
        return
    keep = {path for v in available_variants(model_id) if v != variant for role, fd, path in iter_files(model_id, v)}
    for role, fd, path in iter_files(model_id, variant):
        if path not in keep:
            with suppress(FileNotFoundError):
                os.remove(path)


def remove_stale_files() -> None:
    """Remove downloaded files that are no longer used by any model, for example, after a model is updated"""
    base = models_dir()
    try:
        entries = os.listdir(base)
    except FileNotFoundError:
        return
    models = grammar_metadata()['models']
    for model_id in entries:
        mdir = os.path.join(base, model_id)
        if model_id not in models:
            with suppress(OSError):
                shutil.rmtree(mdir)
            continue
        wanted = {os.path.basename(path) for v in available_variants(model_id) for role, fd, path in iter_files(model_id, v)}
        with suppress(OSError):
            for name in os.listdir(mdir):
                if name not in wanted:
                    with suppress(OSError):
                        os.remove(os.path.join(mdir, name))


def develop() -> None:
    import sys

    model_id = sys.argv[-2] if len(sys.argv) > 2 else 'gec-t5-small'
    variant: Variant = 'gpu' if sys.argv[-1] == 'gpu' else 'cpu'
    print('Downloading', model_id, variant, 'to', models_dir())

    def progress(received: int, total: int) -> None:
        print(f'\r{100 * received / max(1, total):.1f}%', end='', flush=True)

    download_model(model_id, variant, progress)
    print()
    print(model_files(model_id, variant))
