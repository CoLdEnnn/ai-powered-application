"""Start the local model server and the browser app; Ctrl+C stops both."""
import argparse
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse
from app.config import Settings
from app.llm import LocalLlamaClient


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',default=str(Path(__file__).parent/'config.json'))
    parser.add_argument('--existing-model-server',action='store_true',help='Use an already running local server. You are responsible for matching its model and context settings.')
    args=parser.parse_args()
    settings=Settings.load(args.config)
    process=None
    client=LocalLlamaClient(settings.llama_base_url,timeout=5)
    try:
        if not args.existing_model_server:
            if client.ready():
                raise RuntimeError('A server already occupies the configured model port. Stop it, choose another port, or explicitly use --existing-model-server.')
            if not settings.llama_server_path.is_file():
                raise FileNotFoundError('llama-server executable not found. Extract an official llama.cpp release, retain its DLLs, and set llama_server_path in config.json.')
            if not settings.model_path.is_file():
                raise FileNotFoundError('Local GGUF not found. Run python scripts/setup_models.py first, or set model_path to your exported adapted GGUF.')
            endpoint=urlparse(settings.llama_base_url)
            command=[str(settings.llama_server_path),'-m',str(settings.model_path),'--alias','aitu-local','--host',endpoint.hostname,'--port',str(endpoint.port),'-c',str(settings.context_size),'-np','1','-t',str(settings.threads),'-b',str(settings.batch_size),'-ub',str(settings.batch_size),'-ngl',str(settings.gpu_layers),'--cache-ram','0']
            print(f'Model variant: {settings.model_variant}; model file: {settings.model_path.name}',flush=True)
            process=subprocess.Popen(command,cwd=settings.llama_server_path.parent)
        deadline=time.monotonic()+180
        while not client.ready():
            if process and process.poll() is not None:
                raise RuntimeError('The local model process exited. Read its output above for missing DLLs, incompatible CPU flags, or model-load errors.')
            if time.monotonic()>deadline:
                raise TimeoutError('The local model did not become ready in 180 seconds.')
            time.sleep(1)
        # A real tokenizer check makes unsupported server versions fail before chat.
        client.count_tokens([{'role':'user','content':'Hello'}])
        from app.main import create_app
        import uvicorn
        print(f'Open http://{settings.host}:{settings.port} in your browser. Each question is independent.',flush=True)
        uvicorn.run(create_app(args.config),host=settings.host,port=settings.port,workers=1)
    except KeyboardInterrupt:
        pass
    except (RuntimeError,FileNotFoundError,ValueError,TimeoutError) as exc:
        print(f'Startup failed: {exc}',file=sys.stderr)
        return 1
    finally:
        client.close()
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
    return 0


if __name__=='__main__':
    raise SystemExit(main())
