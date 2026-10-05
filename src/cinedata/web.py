"""API local para a interface React; reutiliza o CLI existente."""
import json
import logging
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BUSY = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    def reply(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_POST(self):
        if self.path != '/api/perguntar':
            return self.reply(404, {'erro': 'Rota não encontrada.'})
        if self.headers.get('Host') not in {'127.0.0.1:8000', 'localhost:8000'}:
            return self.reply(403, {'erro': 'Host não permitido.'})
        origin = self.headers.get('Origin')
        if origin and origin not in {'http://127.0.0.1:5173', 'http://localhost:5173'}:
            return self.reply(403, {'erro': 'Origem não permitida.'})
        if self.headers.get('Content-Type', '').split(';')[0].strip() != 'application/json':
            return self.reply(415, {'erro': 'Envie JSON.'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 20000:
                raise ValueError()
            data = json.loads(self.rfile.read(length))
            question = data.get('pergunta') if isinstance(data, dict) else None
            if not isinstance(question, str) or not 1 <= len(question.strip()) <= 2000:
                raise ValueError()
        except (ValueError, UnicodeDecodeError):
            return self.reply(400, {'erro': 'Informe uma pergunta de até 2.000 caracteres.'})
        if not BUSY.acquire(blocking=False):
            return self.reply(409, {'erro': 'Uma consulta está em andamento. Aguarde sua conclusão.'})
        try:
            # Sem shell: a pergunta é um argumento, nunca um comando.
            result = subprocess.run(
                [sys.executable, '-m', 'cinedata.agente', '--json', '--', question.strip()],
                capture_output=True, text=True,
            )
            if result.returncode:
                logging.error('Agente falhou: %s', result.stderr)
                return self.reply(502, {'erro': 'O agente não concluiu a consulta. Veja o terminal da API.'})
            output = json.loads(result.stdout)
            if not isinstance(output, dict) or not {'sql', 'resultado'} <= output.keys():
                raise ValueError('Saída inesperada do agente')
            self.reply(200, output)
        except Exception:
            logging.exception('Falha ao consultar o agente')
            self.reply(502, {'erro': 'Não foi possível obter uma resposta válida. Veja o terminal da API.'})
        finally:
            BUSY.release()


def main():
    logging.basicConfig(level=logging.INFO)
    server = ThreadingHTTPServer(('127.0.0.1', 8000), Handler)
    print('API CineData em http://127.0.0.1:8000', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
