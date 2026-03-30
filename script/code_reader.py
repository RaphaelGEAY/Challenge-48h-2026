import json

def read_code(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)
        code = data['content']
        execute_code(code)
    
def execute_code(code):
    exec(code)