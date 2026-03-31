const { spawn } = require('child_process');
const path = require('path');
const cwd = path.resolve(__dirname, '..');

const pyCode = `from Game.main import main
from Game.storage import load_game_catalog
from Game.tester import display_laby, tester

catalog, levels = load_game_catalog()

level_key = levels[0]
code = catalog[level_key]['default_code']
laby = catalog[level_key]['maze']

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

print('=== display_laby from Game.tester ===')
display_laby(laby, start)
print() 
print('=== tester from Game.tester ===')
tester(code, laby)
print('=== main from Game/main.py ===')
main()`;

const python = spawn('python', ['-c', pyCode], { cwd, stdio: 'inherit' });

python.on('close', (code) => {
  process.exit(code);
});
