import json

def read_code(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        data = json.load(file)
        code = data.get('content', '')
        return code

def read_laby(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        data = json.load(file)
        laby = data.get('maze', [])
        return laby