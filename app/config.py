from dataclasses import dataclass
import ipaddress
import json
from pathlib import Path
from urllib.parse import urlparse


def require_loopback_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != 'http' or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('llama_base_url must be a plain local http URL without credentials or query parameters.')
    try:
        local = ipaddress.ip_address(parsed.hostname or '').is_loopback
    except ValueError:
        local = False
    if not local or parsed.path not in ('', '/'):
        raise ValueError('Use a numeric loopback address such as http://127.0.0.1:8081. Remote generation endpoints are disabled.')
    if not parsed.port:
        raise ValueError('llama_base_url must include the local server port.')
    return value.rstrip('/')


@dataclass(frozen=True)
class Settings:
    root: Path
    model_path: Path
    model_variant: str
    llama_server_path: Path
    llama_base_url: str
    host: str
    port: int
    context_size: int
    threads: int
    gpu_layers: int
    batch_size: int
    max_new_tokens: int
    temperature: float
    top_p: float
    seed: int
    retrieval_k: int
    min_similarity: float | None
    embedding_model: str
    embedding_threads: int
    embedding_cache: Path
    index_dir: Path
    corpus_path: Path
    source_catalog_path: Path
    system_prompt_path: Path
    request_timeout_seconds: int
    max_question_chars: int

    @classmethod
    def load(cls, filename: str | Path = 'config.json') -> 'Settings':
        config_path = Path(filename).resolve()
        raw = json.loads(config_path.read_text(encoding='utf-8'))
        root = config_path.parent
        expected = set(cls.__dataclass_fields__) - {'root'}
        if set(raw) != expected:
            raise ValueError(f'Configuration keys differ: missing={sorted(expected-set(raw))}; unknown={sorted(set(raw)-expected)}')
        for field in ('model_path','llama_server_path','embedding_cache','index_dir','corpus_path','source_catalog_path','system_prompt_path'):
            raw[field] = (root / raw[field]).resolve()
        raw['llama_base_url'] = require_loopback_url(raw['llama_base_url'])
        if raw['host'] != '127.0.0.1':
            raise ValueError('This local prototype binds to 127.0.0.1. Add authentication before designing a shared server deployment.')
        for key in ('port','context_size','threads','batch_size','max_new_tokens','retrieval_k','embedding_threads','request_timeout_seconds','max_question_chars'):
            if type(raw[key]) is not int or raw[key] <= 0:
                raise ValueError(f'{key} must be a positive integer.')
        if raw['context_size'] < raw['max_new_tokens'] + 256:
            raise ValueError('context_size must leave room for both the prompt and generated answer.')
        if not 0 <= raw['temperature'] <= 2 or not 0 < raw['top_p'] <= 1:
            raise ValueError('Invalid temperature or top_p.')
        if raw['min_similarity'] is not None and not -1 <= raw['min_similarity'] <= 1:
            raise ValueError('min_similarity must be null or a cosine threshold between -1 and 1.')
        if raw['model_variant'] not in ('baseline','adapted'):
            raise ValueError('model_variant must be baseline or adapted.')
        if raw['port'] == urlparse(raw['llama_base_url']).port:
            raise ValueError('The web app and model server need different ports.')
        return cls(root=root, **raw)
