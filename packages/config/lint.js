import tseslint from 'typescript-eslint';
import {
  ignores as baseIgnores,
  recommended,
  strictTsBlock,
  typeCheckedLanguageOptions,
  commentPlugins,
  COMMENT_RULES,
  QUOTES,
} from './eslint/base.js';

const DEFAULT_TEST_FILES = ['**/test/**', '**/*.{test,spec}.{ts,tsx}', '**/*.test.*'];

function prefixGlob(dir, glob) {
  if (dir === '.') return glob;
  if (glob.startsWith('!')) return '!' + prefixGlob(dir, glob.slice(1));
  return `${dir}/${glob}`;
}

function scopeBlock(dir, block) {
  if (dir === '.') return { ...block };
  const out = { ...block };
  if (Array.isArray(block.ignores)) {
    out.ignores = block.ignores.map((g) => prefixGlob(dir, g));
  }
  if (Array.isArray(block.files)) {
    out.files = block.files.map((g) => prefixGlob(dir, g));
  } else if (!Array.isArray(block.ignores)) {
    out.files = [prefixGlob(dir, '**/*.{ts,tsx,mts,cts,js,jsx,mjs,cjs}')];
  }
  return out;
}

function scopePreset(dir, preset) {
  return preset.map((block) => scopeBlock(dir, block));
}

function libraryPreset(rootDir, files) {
  return [
    baseIgnores(),
    { files: ['**/*.{ts,tsx}'], languageOptions: typeCheckedLanguageOptions(rootDir) },
    ...recommended,
    strictTsBlock({ files, tsconfigRootDir: rootDir }),
  ];
}

function presetFor(workspace, rootDir) {
  const files = workspace.src ?? ['src/**/*.{ts,tsx}'];
  return libraryPreset(rootDir, files);
}

export function buildLintConfig(stageConfig, cwd) {
  const rootDir = cwd ?? process.cwd();
  const entries = Object.entries(stageConfig.workspaces);

  const config = [{ ignores: ['**/node_modules/**', '**/dist/**', '**/.vite/**'] }];

  const repoEslint = stageConfig.eslint ?? {};
  if (Array.isArray(repoEslint.ignores) && repoEslint.ignores.length > 0) {
    config.push({ ignores: repoEslint.ignores });
  }

  for (const [path, workspace] of entries) {
    const wsEslint = workspace.eslint ?? {};
    if (Array.isArray(wsEslint.ignores) && wsEslint.ignores.length > 0) {
      config.push({ ignores: wsEslint.ignores.map((g) => prefixGlob(path, g)) });
    }
    const hasExtends = Array.isArray(wsEslint.extends) && wsEslint.extends.length > 0;
    if (wsEslint.preset === 'none') {
      if (hasExtends && path !== '.') {
        config.push(
          scopeBlock(path, { files: ['**/*.{ts,tsx}'], languageOptions: typeCheckedLanguageOptions(rootDir) }),
        );
      }
    } else {
      config.push(...scopePreset(path, presetFor(workspace, rootDir)));
    }
    if (hasExtends) {
      config.push(...scopePreset(path, wsEslint.extends));
    }
    if (wsEslint.rules && typeof wsEslint.rules === 'object') {
      config.push(scopeBlock(path, { files: ['**/*.{ts,tsx}'], rules: wsEslint.rules }));
    }
  }

  if (Array.isArray(repoEslint.extends)) {
    config.push(...repoEslint.extends);
  }

  config.push(
    { files: ['**/*.{js,jsx,cjs,mjs}'], ...tseslint.configs.disableTypeChecked },
    { files: ['**/*.config.{ts,mts,cts}'], ...tseslint.configs.disableTypeChecked },
  );
  config.push({ files: ['**/*.{js,jsx,cjs,mjs}'], plugins: commentPlugins, rules: { ...COMMENT_RULES } });
  config.push({ files: ['**/*.{js,jsx,cjs,mjs}'], rules: { quotes: QUOTES } });

  if (repoEslint.rules && typeof repoEslint.rules === 'object') {
    config.push({ rules: repoEslint.rules });
  }

  const testFiles =
    Array.isArray(repoEslint.testFiles) && repoEslint.testFiles.length > 0
      ? repoEslint.testFiles
      : DEFAULT_TEST_FILES;
  config.push({
    files: testFiles,
    languageOptions: { parserOptions: { projectService: false, project: false } },
    plugins: commentPlugins,
    rules: { ...tseslint.configs.disableTypeChecked.rules, ...COMMENT_RULES, quotes: QUOTES },
  });

  return config;
}
