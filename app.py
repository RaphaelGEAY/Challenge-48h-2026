from flask import Flask, jsonify, request, send_from_directory, Response, stream_with_context
import ast
import json
import os
import threading
import queue
from script.code_reader import read_code, read_laby
from script.tester import tester

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, 'maze.json')
DATA_LOCK = threading.Lock()

SAFE_BUILTINS = {
    'range': range,
    'len': len,
    'enumerate': enumerate,
    'min': min,
    'max': max,
    'abs': abs,
    'sum': sum,
}

BANNED_CALLS = {'open', 'exec', 'eval', 'compile', '__import__', 'input'}
BANNED_MODULES = {'os', 'sys', 'subprocess', 'pathlib', 'shutil', 'socket'}

app = Flask(__name__, static_folder='.', static_url_path='')


def load_json():
    with open(DATA_FILE, 'r', encoding='utf-8') as file:
        return json.load(file)


def save_json(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


def update_json(mutator):
    with DATA_LOCK:
        data = load_json()
        mutator(data)
        save_json(data)


def api_error(message, status=500, details=None):
    payload = {'error': message}
    if details and app.debug:
        payload['details'] = details
    return jsonify(payload), status


def parse_json_payload(required_field=None):
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ValueError('Invalid JSON body')
    if required_field and required_field not in payload:
        raise ValueError(f'Missing {required_field} field')
    return payload


def validate_user_code(code):
    try:
        tree = ast.parse(code, mode='exec')
    except SyntaxError as exc:
        raise ValueError(f'Syntax error: {exc.msg} (line {exc.lineno})') from exc

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise ValueError('Imports are not allowed in submitted code')

        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in BANNED_CALLS:
            raise ValueError(f"Forbidden function call: {node.func.id}")

        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in BANNED_MODULES:
            raise ValueError(f"Forbidden module usage: {node.value.id}")


@app.route('/')
def index():
    return send_from_directory('.', 'test.html')


@app.route('/api/maze', methods=['GET'])
def api_maze():
    try:
        with DATA_LOCK:
            maze = read_laby(DATA_FILE)
        return jsonify({'maze': maze})
    except Exception as exc:
        return api_error('Failed to load maze', details=str(exc))


@app.route('/api/code', methods=['GET'])
def api_code():
    try:
        with DATA_LOCK:
            code = read_code(DATA_FILE)
        return jsonify({'content': code})
    except Exception as exc:
        return api_error('Failed to load code', details=str(exc))


@app.route('/api/code', methods=['PUT'])
def api_save_code():
    try:
        payload = parse_json_payload(required_field='content')
        update_json(lambda data: data.__setitem__('content', payload['content']))
        return jsonify({'ok': True})
    except ValueError as exc:
        return api_error(str(exc), status=400)
    except Exception as exc:
        return api_error('Failed to save code', details=str(exc))


@app.route('/api/maze', methods=['PUT'])
def api_save_maze():
    try:
        payload = parse_json_payload(required_field='maze')
        if not isinstance(payload['maze'], list):
            return api_error('maze must be a list', status=400)
        update_json(lambda data: data.__setitem__('maze', payload['maze']))
        return jsonify({'ok': True})
    except ValueError as exc:
        return api_error(str(exc), status=400)
    except Exception as exc:
        return api_error('Failed to save maze', details=str(exc))


@app.route('/api/run-tester', methods=['POST'])
def api_run_tester():
    try:
        payload = request.get_json(silent=True) or {}
        with DATA_LOCK:
            code = payload.get('content') if isinstance(payload, dict) and 'content' in payload else read_code(DATA_FILE)
            laby = read_laby(DATA_FILE)
        validate_user_code(code)
        if not isinstance(laby, list) or not laby:
            return api_error('Invalid maze format', status=400)
    except Exception as exc:
        return api_error(str(exc), status=400)

    event_queue = queue.Queue()
    sentinel = object()

    def worker():
        result = tester(
            code,
            laby,
            return_history=True,
            exec_globals={'__builtins__': SAFE_BUILTINS},
        )

        for trace in result.get('trace', []):
            event_queue.put({
                'type': 'trace',
                'lineno': trace.get('lineno'),
                'line': trace.get('line', ''),
                'position': trace.get('position'),
            })

        current = result.get('current')
        if current is not None:
            current = list(current)

        event_queue.put({
            'type': 'done',
            'error': result.get('error'),
            'status': result.get('status', 'failed'),
            'message': result.get('message', 'Execution terminee'),
            'current': current,
        })
        event_queue.put(sentinel)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    def stream():
        while True:
            item = event_queue.get()
            if item is sentinel:
                break
            yield json.dumps(item) + '\n'

    return Response(stream_with_context(stream()), mimetype='application/x-ndjson')


if __name__ == '__main__':
    debug_mode = os.getenv('FLASK_DEBUG', '0').lower() in ('1', 'true', 'yes', 'on')
    app.run(debug=debug_mode)
