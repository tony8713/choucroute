import { defineConfig } from '@choucroute/config';

export default defineConfig({
  workspaces: {
    'packages/config': {
      type: 'library',
      eslint: { preset: 'none' },
    },
    'packages/kit': {
      type: 'library',
    },
    'apps/ui': {
      type: 'react',
      src: ['src/**/*.{ts,tsx}'],
    },
  },
  eslint: {
    ignores: [
      'tools/**',
      'scratch/**',
      'image/**',
      'models/**',
      'common/**',
      'orin/**',
      'satellite/**',
      'daemon/**',
      'docs/**',
      'hardware/**',
      'tests/**',
      '__pycache__/**',
      'harness_twotier.py',
    ],
  },
  madge: {
    roots: ['packages/kit/src', 'apps/ui/src'],
  },
});
