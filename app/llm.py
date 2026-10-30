"""HTTP transport to a model running on this computer; no cloud SDK."""
import httpx
from .config import require_loopback_url


class LocalModelError(RuntimeError):
    pass


class LocalLlamaClient:
    def __init__(self, base_url: str, timeout: float = 240):
        self.base_url = require_loopback_url(base_url)
        self.client = httpx.Client(base_url=self.base_url, timeout=timeout, follow_redirects=False, trust_env=False)

    def close(self):
        self.client.close()

    def _post(self, endpoint: str, payload: dict) -> dict:
        try:
            response = self.client.post(endpoint, json=payload)
            response.raise_for_status()
            result = response.json()
            if not isinstance(result, dict):
                raise ValueError('Expected a JSON object.')
            return result
        except (httpx.HTTPError, ValueError) as exc:
            raise LocalModelError(f'Local model request failed at {endpoint}. Check the model-server terminal and installed llama.cpp version.') from exc

    def ready(self) -> bool:
        try:
            return self.client.get('/health', timeout=2).status_code == 200
        except httpx.HTTPError:
            return False

    def count_tokens(self, messages: list[dict]) -> int:
        formatted = self._post('/apply-template', {'messages':messages})
        prompt = formatted.get('prompt')
        if not isinstance(prompt, str):
            raise LocalModelError('The model server did not return a formatted chat prompt.')
        result = self._post('/tokenize', {'content':prompt,'add_special':False,'parse_special':True,'with_pieces':False})
        tokens = result.get('tokens')
        if not isinstance(tokens,list):
            raise LocalModelError('The model server did not return a token list.')
        return len(tokens)

    def complete(self, messages: list[dict], *, max_tokens: int, temperature: float, top_p: float, seed: int) -> dict:
        result = self._post('/v1/chat/completions', {
            'model':'aitu-local','messages':messages,'max_tokens':max_tokens,
            'temperature':temperature,'top_p':top_p,'seed':seed,'stream':False,
        })
        try:
            choice = result['choices'][0]
            answer = choice['message']['content']
            if not isinstance(answer,str) or not answer.strip():
                raise ValueError('Empty answer.')
            return {'answer':answer.strip(),'usage':result.get('usage',{}),'finish_reason':choice.get('finish_reason'),'model':result.get('model','aitu-local')}
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise LocalModelError('The local model returned no usable answer.') from exc
