import json

def read_code(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)
        code = data['content']
        return code

def read_laby(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)
        laby = data['maze']
        return laby