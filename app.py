from flask import Flask, jsonify, request, send_from_directory, abort, Response, stream_with_context
import json
import os
import io
import sys
import subprocess
import contextlib
import time
import threading
import queue
from script.code_reader import read_code, read_laby
from script.tester import tester

DATA_FILE = 'maze.json'

app = Flask(__name__, static_folder='.', static_url_path='')


def load_json():
    with open(DATA_FILE, 'r', encoding='utf-8') as file:
        return json.load(file)


def save_json(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


@app.route('/')
def index():
    return send_from_directory('.', 'test.html')


@app.route('/api/maze', methods=['GET'])
def api_maze():
    try:
        maze = read_laby(DATA_FILE)
        return jsonify({'maze': maze})
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


@app.route('/api/code', methods=['GET'])
def api_code():
    try:
        code = read_code(DATA_FILE)
        return jsonify({'content': code})
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


@app.route('/api/code', methods=['PUT'])
def api_save_code():
    payload = request.get_json(force=True)
    if payload is None or 'content' not in payload:
        return jsonify({'error': 'Missing content field'}), 400

    try:
        data = load_json()
        data['content'] = payload['content']
        save_json(data)
        return jsonify({'ok': True})
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


@app.route('/api/maze', methods=['PUT'])
def api_save_maze():
    payload = request.get_json(force=True)
    if payload is None or 'maze' not in payload:
        return jsonify({'error': 'Missing maze field'}), 400

    try:
        data = load_json()
        data['maze'] = payload['maze']
        save_json(data)
        return jsonify({'ok': True})
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


@app.route('/api/run-tester', methods=['POST'])
def api_run_tester():
    try:
        payload = request.get_json(silent=True) or {}
        code = payload.get('content') if isinstance(payload, dict) and 'content' in payload else read_code(DATA_FILE)
        laby = read_laby(DATA_FILE)
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500

    event_queue = queue.Queue()
    sentinel = object()
    code_lines = code.splitlines()
    current_pos = [None]

    def move(direction):
        moves = {
            'left': (0, -1),
            'right': (0, 1),
            'up': (-1, 0),
            'down': (1, 0),
        }
        if direction not in moves:
            raise ValueError("Direction invalide. Utilise: left, right, up, down")
        dx, dy = moves[direction]
        x, y = current_pos[0]
        nx, ny = x + dx, y + dy
        if not (0 <= nx < len(laby) and 0 <= ny < len(laby[0])):
            raise ValueError(f"Sortie des limites: {(nx, ny)}")
        if laby[nx][ny] == '#':
            raise ValueError(f"Mur rencontre: {(nx, ny)}")
        current_pos[0] = (nx, ny)
        return current_pos[0]

    def tracer(frame, event, arg):
        if event == 'line' and frame.f_code.co_filename == '<string>':
            lineno = frame.f_lineno
            line = code_lines[lineno - 1] if 1 <= lineno <= len(code_lines) else ''
            event_queue.put({
                'type': 'trace',
                'lineno': lineno,
                'line': line,
                'position': list(current_pos[0]) if current_pos[0] is not None else None,
            })
        return tracer

    def worker():
        start = None
        for i in range(len(laby)):
            for j in range(len(laby[i])):
                if laby[i][j] in ('S', 'P'):
                    start = (i, j)
                    break
            if start is not None:
                break
        current_pos[0] = start
        error = None
        try:
            sys.settrace(tracer)
            exec(code, {'laby': laby, 'move': move})
        except Exception as exc:
            error = str(exc)
        finally:
            sys.settrace(None)
            if current_pos[0] is None:
                status = 'failed'
                message = 'Depart introuvable ou erreur inconnue'
            else:
                x, y = current_pos[0]
                status = 'success' if laby[x][y] == 'O' else 'failed'
                message = 'Arrivee atteinte' if status == 'success' else f"Arrivee non atteinte. Position finale: {current_pos[0]}"
            event_queue.put({
                'type': 'done',
                'error': error,
                'status': status,
                'message': message,
                'current': list(current_pos[0]) if current_pos[0] is not None else None,
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


@app.route('/api/run-main', methods=['POST'])
def api_run_main():
    try:
        result = subprocess.run(
            [sys.executable, 'main.py'],
            cwd=os.getcwd(),
            capture_output=True,
            text=True,
            timeout=15,
        )
        return jsonify({
            'stdout': result.stdout,
            'stderr': result.stderr,
            'returncode': result.returncode,
        })
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'main.py execution timed out'}), 500
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


if __name__ == '__main__':
    app.run(debug=True)
