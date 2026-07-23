#!/usr/bin/env node
import { existsSync, mkdtempSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { resolve, join } from 'node:path';
import { tmpdir } from 'node:os';
import { pathToFileURL } from 'node:url';
import { spawnSync } from 'node:child_process';

const requireFromCwd = createRequire(join(process.cwd(), 'noop.js'));

function resolvePkg(specifier) {
  return pathToFileURL(requireFromCwd.resolve(specifier)).href;
}

const SUBS = ['lint', 'madge', 'typecheck'];

function usage(message) {
  if (message) process.stderr.write(`${message}\n`);
  process.stderr.write(`usage: choucroute <${SUBS.join('|')}> [...args]\n`);
  process.exit(1);
}

const cwd = process.cwd();

function configPath() {
  const p = resolve(cwd, 'choucroute.config.js');
  if (!existsSync(p)) {
    process.stderr.write(`choucroute: no choucroute.config.js found in ${cwd}\n`);
    process.exit(1);
  }
  return p;
}

async function loadConfig() {
  const p = configPath();
  const mod = await import(pathToFileURL(p).href);
  return mod.default ?? mod.config ?? mod;
}

function localBin(name) {
  let dir = cwd;
  for (;;) {
    const candidate = resolve(dir, 'node_modules', '.bin', name);
    if (existsSync(candidate)) return candidate;
    const parent = resolve(dir, '..');
    if (parent === dir) break;
    dir = parent;
  }
  return name;
}

function run(bin, args) {
  const res = spawnSync(bin, args, { stdio: 'inherit', cwd });
  return res.status ?? 1;
}

function firstExisting(names) {
  for (const name of names) {
    if (existsSync(resolve(cwd, name))) return name;
  }
  return null;
}

function writeTemp(prefix, contents) {
  const dir = mkdtempSync(join(tmpdir(), prefix));
  const file = join(dir, 'config.mjs');
  writeFileSync(file, contents);
  return file;
}

function configUrl() {
  return pathToFileURL(configPath()).href;
}

function cmdLint(argv) {
  const native = firstExisting(['eslint.config.js', 'eslint.config.mjs', 'eslint.config.cjs']);
  if (native) {
    process.stderr.write(`choucroute lint: deferring to native ${native}\n`);
    return run(localBin('eslint'), ['.', ...argv]);
  }
  const temp = writeTemp('choucroute-lint-', [
    `import { buildLintConfig } from ${JSON.stringify(resolvePkg('@choucroute/config/lint'))};`,
    `import cfg from ${JSON.stringify(configUrl())};`,
    `export default buildLintConfig(cfg, ${JSON.stringify(cwd)});`,
    '',
  ].join('\n'));
  return run(localBin('eslint'), ['--config', temp, '.', ...argv]);
}

function globToDir(glob) {
  const idx = glob.indexOf('*');
  let base = idx === -1 ? glob : glob.slice(0, idx);
  base = base.replace(/\/+$/, '');
  return base || '.';
}

function prefixed(path, dir) {
  if (path === '.') return dir;
  if (dir === '.') return path;
  return `${path}/${dir}`;
}

async function cmdMadge(config, argv) {
  const { madgeConfig } = await import('@choucroute/config/madge');
  const { default: madge } = await import('madge');
  let roots;
  if (argv.length > 0) {
    roots = argv;
  } else if (Array.isArray(config.madge?.roots) && config.madge.roots.length > 0) {
    roots = config.madge.roots;
  } else {
    roots = [];
    for (const [path, workspace] of Object.entries(config.workspaces)) {
      if (Array.isArray(workspace.src) && workspace.src.length > 0) {
        for (const g of workspace.src) roots.push(prefixed(path, globToDir(g)));
      } else {
        roots.push(path === '.' ? 'src' : `${path}/src`);
      }
    }
  }
  roots = roots.filter((r) => existsSync(resolve(cwd, r)));
  const res = await madge(roots, madgeConfig);
  const circular = res.circular();
  if (circular.length === 0) {
    process.stdout.write(`madge: no circular dependencies found across ${roots.length} source ${roots.length === 1 ? 'root' : 'roots'}.\n`);
    return 0;
  }
  process.stdout.write(`madge: ${circular.length} circular dependenc${circular.length === 1 ? 'y' : 'ies'} found:\n\n`);
  for (const cycle of circular) process.stdout.write('  ' + cycle.join(' -> ') + '\n');
  return 1;
}

function cmdTypecheck(config, argv) {
  const failures = [];
  for (const [path] of Object.entries(config.workspaces)) {
    const project = path === '.' ? 'tsconfig.json' : `${path}/tsconfig.json`;
    if (!existsSync(resolve(cwd, project))) continue;
    process.stdout.write(`choucroute typecheck: ${path} (tsc)\n`);
    const status = run(localBin('tsc'), ['--noEmit', '-p', project, ...argv]);
    if (status !== 0) failures.push(path);
  }
  if (failures.length > 0) {
    process.stderr.write(`choucroute typecheck: failed in ${failures.join(', ')}\n`);
    return 1;
  }
  return 0;
}

async function main() {
  const [sub, ...argv] = process.argv.slice(2);
  if (!sub || !SUBS.includes(sub)) {
    usage(sub ? `choucroute: unknown command "${sub}"` : null);
  }
  let status = 1;
  if (sub === 'lint') {
    configPath();
    status = cmdLint(argv);
  } else if (sub === 'madge') {
    status = await cmdMadge(await loadConfig(), argv);
  } else if (sub === 'typecheck') {
    status = cmdTypecheck(await loadConfig(), argv);
  }
  process.exit(status);
}

await main();
