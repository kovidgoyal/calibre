#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

# Deciding whether to run grammar models on the GPU. There are three modes:
#   off:  always use the CPU
#   on:   use any available hardware accelerated execution provider, falling
#         back to the CPU if it fails
#   auto: use the GPU only with execution providers that are known to work
#         well on this platform, for models that benefit from it, and only if
#         a previous attempt did not show it to be unusable or slower than the CPU.

import json
import os
import sys
from contextlib import suppress
from functools import lru_cache
from threading import Lock
from typing import Literal, TypedDict, get_args

GpuMode = Literal['auto', 'on', 'off']
GPU_MODES: tuple[GpuMode, ...] = get_args(GpuMode)
DEFAULT_GPU_MODE: GpuMode = 'auto'
# The minimum fraction of the nodes of a model that must run on the GPU for
# auto mode to use it. Nodes the GPU does not support run on the CPU, which
# requires copying data between them.
MIN_FRACTION_ON_GPU = 0.9
decisions_lock = Lock()


class GpuDecision(TypedDict):
    use_gpu: bool
    reason: str
    gpu_ms: float  # time for a benchmark run on the GPU, zero if not measured
    cpu_ms: float  # time for a benchmark run on the CPU, zero if not measured


def gpu_mode_from_string(x: str | None) -> GpuMode:
    for m in GPU_MODES:
        if m == x:
            return m
    return DEFAULT_GPU_MODE


@lru_cache(2)
def gpu_providers() -> tuple[str, ...]:
    """The hardware accelerated execution providers available, in order of preference. Empty if querying them fails."""
    from calibre_extensions.seq2seq import gpu_providers as gp

    try:
        return tuple(gp())
    except OSError:
        return ()


def is_apple_silicon() -> bool:
    import platform

    return sys.platform == 'darwin' and platform.machine() == 'arm64'


def auto_providers() -> tuple[str, ...]:
    """Providers that are expected to work well enough to be used automatically"""
    if sys.platform == 'win32':
        good = {'DmlExecutionProvider'}
    elif sys.platform == 'darwin':
        # On Intel Macs CoreML mostly runs models on the CPU
        good = {'CoreMLExecutionProvider'} if is_apple_silicon() else set()
    else:
        good = {'CUDAExecutionProvider', 'TensorRTExecutionProvider'}
    return tuple(p for p in gpu_providers() if p in good)


def providers_for_mode(mode: GpuMode) -> tuple[str, ...]:
    if mode == 'off':
        return ()
    return gpu_providers() if mode == 'on' else auto_providers()


def onnxruntime_version() -> str:
    from calibre_extensions.seq2seq import onnxruntime_version as v

    return v()


def decisions_path() -> str:
    from calibre.constants import cache_dir

    return os.path.join(cache_dir(), 'grammar', 'gpu-decisions.json')


def decision_key(model_id: str, model_hash: str, provider: str) -> str:
    # Include the onnxruntime version so that decisions are re-evaluated when
    # it is upgraded, as newer versions often support more operators
    return f'{model_id}:{model_hash[:16]}:{provider}:{onnxruntime_version()}'


def read_decisions() -> dict[str, GpuDecision]:
    try:
        with open(decisions_path(), 'rb') as f:
            ans: dict[str, GpuDecision] = json.loads(f.read())
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        print('Failed to read GPU decisions for grammar models with error:', e, file=sys.stderr)
        return {}
    return ans if isinstance(ans, dict) else {}


def get_decision(model_id: str, model_hash: str, provider: str) -> GpuDecision | None:
    with decisions_lock:
        return read_decisions().get(decision_key(model_id, model_hash, provider))


def set_decision(model_id: str, model_hash: str, provider: str, decision: GpuDecision) -> None:
    from calibre.utils.filenames import atomic_rename

    with decisions_lock:
        d = read_decisions()
        d[decision_key(model_id, model_hash, provider)] = decision
        path = decisions_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + f'.{os.getpid()}.tmp'
        try:
            with open(tmp, 'w') as f:
                json.dump(d, f, indent=2)
            atomic_rename(tmp, path)
        except OSError as e:
            print('Failed to save GPU decision for grammar models with error:', e, file=sys.stderr)
            with suppress(OSError):
                os.remove(tmp)


def clear_decisions() -> None:
    with decisions_lock, suppress(FileNotFoundError):
        os.remove(decisions_path())
