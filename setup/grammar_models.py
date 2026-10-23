#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

import hashlib
import json
import os

from setup.revendor import ReVendor

# The models used for grammar checking and sentence improvement suggestions.
# Each model has a variant for running on the CPU (quantized to int8) and
# optionally one for running on the GPU (full precision, as GPU execution
# providers do not support the dynamically quantized operators). The files
# come from ONNX exports on Hugging Face, pinned to specific revisions. Change
# these and run ./setup.py grammar_models to update.

GEC_T5_SMALL = {
    'name': 'GEC T5 small',
    'description': 'A small, fast model for detecting and correcting grammatical errors in English',
    'source': 'https://huggingface.co/Unbabel/gec-t5_small',
    'license': 'Apache-2.0 (the model was trained on the cLang-8 dataset, which is licensed for non-commercial use only)',
    'attribution': 'Unbabel, based on "A Simple Recipe for Multilingual Grammatical Error Correction" by Rothe et al.',
    'languages': ['en'],
    'prompts': {'check': 'gec: '},
    'max_length': 256,
    # Whether to use the GPU variant when the GPU setting is auto. Small models
    # gain little from the GPU and the transfer overhead can make them slower.
    'auto_gpu': False,
    'variants': {
        'cpu': {
            'repo': 'TonyRaju/gec-t5-small-coedit-onnx-int8',
            'revision': '1b76cab579f033f1da0e6c98557beeab5d33dd5b',
            'files': {
                'encoder': 'encoder_model.onnx',
                'decoder': 'decoder_model.onnx',
                'decoder_with_past': 'decoder_with_past_model.onnx',
                'tokenizer': 'tokenizer.json',
            },
        },
        'gpu': {
            'repo': 'JonaWhisper/jonawhisper-gec-t5-small-onnx',
            'revision': '240e0e34d7638690212367d9ecfcd501c9327cc9',
            'files': {
                'encoder': 'encoder_model.onnx',
                'decoder': 'decoder_model.onnx',
                'tokenizer': 'tokenizer.json',
            },
        },
    },
}

COEDIT_LARGE = {
    'name': 'CoEdIT large',
    'description': 'A large model for rewriting English sentences to fix grammar, or make them more fluent, clearer, simpler or more formal',
    'source': 'https://huggingface.co/grammarly/coedit-large',
    'license': 'CC-BY-NC-4.0 (non-commercial use only)',
    'attribution': 'Grammarly, from "CoEdIT: Text Editing by Task-Specific Instruction Tuning" by Raheja et al.',
    'languages': ['en'],
    'prompts': {
        'check': 'Fix grammatical errors in this sentence: ',
        'grammar': 'Fix grammatical errors in this sentence: ',
        'fluency': 'Make this sentence fluent: ',
        'clarity': 'Make this sentence clearer: ',
        'simplify': 'Write a simpler version for the sentence: ',
        'formal': 'Make the sentence more formal: ',
        'paraphrase': 'Paraphrase this sentence: ',
    },
    'max_length': 256,
    'auto_gpu': True,
    'variants': {
        'cpu': {
            'repo': 'rayliuca/coedit-large-onnx-quantized',
            'revision': 'df89602e624c29e2bfc9e411a122c4c2088f1517',
            'files': {
                'encoder': 'encoder_model_quantized.onnx',
                'decoder': 'decoder_model_quantized.onnx',
                'decoder_with_past': 'decoder_with_past_model_quantized.onnx',
                'tokenizer': 'tokenizer.json',
            },
        },
        'gpu': {
            'repo': 'imrahamed/coedit-large-webgpu-onnx',
            'revision': '0ca35bb9227094c329ee4e30f5de0dce597dfa20',
            'files': {
                'encoder': 'onnx/encoder_model.onnx',
                'decoder': 'onnx/decoder_model_merged.onnx',
                'tokenizer': 'tokenizer.json',
            },
        },
    },
}

MODELS = {'gec-t5-small': GEC_T5_SMALL, 'coedit-large': COEDIT_LARGE}

# The default model for each task and language
DEFAULTS = {
    'check': {'en': 'gec-t5-small'},
    'suggest': {'en': 'coedit-large'},
}

# The token ids used by T5 models
T5_SPECIAL_TOKENS = {'decoder_start_token_id': 0, 'eos_token_id': 1, 'pad_token_id': 0}


class GrammarModels(ReVendor):
    description = 'Generate the list of grammar checking models with pinned download URLs and hashes'
    NAME = 'grammar_models'
    TAR_NAME = 'grammar model list'
    VERSION = '1'
    DOWNLOAD_URL = 'https://huggingface.co'
    CAN_USE_SYSTEM_VERSION = False

    @property
    def output_file_path(self) -> str:
        return os.path.join(self.RESOURCES, 'grammar-models.json')

    def hf_tree(self, repo: str, revision: str) -> dict[str, dict[str, object]]:
        url = f'https://huggingface.co/api/models/{repo}/tree/{revision}?recursive=true'
        items: list[dict[str, object]] = json.loads(self.download_securely(url))
        return {str(x['path']): x for x in items if x.get('type') == 'file'}

    def file_data(self, repo: str, revision: str, path: str, tree: dict[str, dict[str, object]]) -> dict[str, object]:
        entry = tree.get(path)
        if entry is None:
            raise SystemExit(f'{path} not found in {repo} at revision {revision}')
        url = f'https://huggingface.co/{repo}/resolve/{revision}/{path}'
        lfs = entry.get('lfs')
        if isinstance(lfs, dict) and lfs.get('oid'):
            return {'url': url, 'sha256': str(lfs['oid']), 'size': int(str(lfs['size']))}
        self.info('Downloading', url)
        data = self.download_securely(url)
        return {'url': url, 'sha256': hashlib.sha256(data).hexdigest(), 'size': len(data)}

    def run(self, opts):
        models = {}
        for model_id, spec in MODELS.items():
            variants = {}
            for variant_name, v in spec['variants'].items():
                self.info(f'Processing {model_id} ({variant_name}) from {v["repo"]}')
                tree = self.hf_tree(v['repo'], v['revision'])
                files = {key: self.file_data(v['repo'], v['revision'], path, tree) for key, path in v['files'].items()}
                for required in ('encoder', 'decoder', 'tokenizer'):
                    if required not in files:
                        raise SystemExit(f'The {variant_name} variant of {model_id} has no {required}')
                files.setdefault('decoder_with_past', None)
                variants[variant_name] = files
            if 'cpu' not in variants:
                raise SystemExit(f'{model_id} has no CPU variant')
            models[model_id] = {
                **{k: v for k, v in spec.items() if k != 'variants'},
                **T5_SPECIAL_TOKENS,
                'variants': variants,
            }
        for task, lang_map in DEFAULTS.items():
            for lang, model_id in lang_map.items():
                if model_id not in models:
                    raise SystemExit(f'The default {task} model for {lang}, {model_id}, does not exist')
                prompts = models[model_id]['prompts']
                if (task == 'check' and 'check' not in prompts) or (task == 'suggest' and not set(prompts) - {'check'}):
                    raise SystemExit(f'The default {task} model for {lang}, {model_id}, does not support the task')
        data = {'version': 1, 'defaults': DEFAULTS, 'models': models}
        with open(self.output_file_path, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write('\n')
        self.info(f'Wrote {len(models)} models to {self.output_file_path}')

    def clean(self):
        # The output is checked into the repository, so it is not removed
        pass
