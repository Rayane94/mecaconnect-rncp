import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, resolve, relative } from 'node:path';

const root = resolve('src');
const rules = [
  ['no-eval', /\beval\s*\(/g],
  ['no-function-constructor', /\bnew\s+Function\s*\(/g],
  ['no-debugger', /\bdebugger\s*;/g],
  ['no-var', /\bvar\s+[A-Za-z_$][\w$]*/g],
  ['no-console-log', /\bconsole\.log\s*\(/g],
];
function* files(dir) {
  for (const name of readdirSync(dir).sort()) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) yield* files(path);
    else if (/\.(ts|tsx|js|mjs)$/.test(name)) yield path;
  }
}
let scanned = 0;
let errors = 0;
for (const path of files(root)) {
  scanned++;
  const contents = readFileSync(path, 'utf8');
  for (const [name, rule] of rules) {
    for (const match of contents.matchAll(rule)) {
      const line = contents.slice(0, match.index).split('\n').length;
      console.error(relative(process.cwd(), path) + ':' + line + ' [' + name + ']');
      errors++;
    }
  }
}
console.info('Lint statique : ' + scanned + ' fichiers, ' + errors + ' anomalie(s).');
if (errors) process.exitCode = 1;
