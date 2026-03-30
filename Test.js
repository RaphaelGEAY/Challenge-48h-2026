const { spawn } = require('child_process');
const path = require('path');
const cwd = __dirname;

const pyCode = `from main import main
from script.code_reader import read_code, read_laby
from script.tester import display_laby, tester

code = read_code('maze.json')
laby = read_laby('maze.json')

start = None
for i, row in enumerate(laby):
    for j, cell in enumerate(row):
        if cell in ('S', 'P'):
            start = (i, j)
            break
    if start is not None:
        break
if start is None:
    start = (0, 0)

print('=== display_laby from script.tester ===')
display_laby(laby, start)
print() 
print('=== tester from script.tester ===')
tester(code, laby)
print('=== main from main.py ===')
main()`;

const python = spawn('python', ['-c', pyCode], { cwd, stdio: 'inherit' });

python.on('close', (code) => {
  process.exit(code);
});
