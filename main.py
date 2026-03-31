from script.code_reader import *
from script.tester import *
if __name__ == '__main__':
    code = read_code('maze.json')
    laby = read_laby('maze.json')
    tester(code, laby)