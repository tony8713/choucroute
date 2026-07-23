import { defineConfig } from '@choucroute/config';

export default defineConfig({
  workspaces: {
    'packages/config': {
      type: 'library',
      eslint: { preset: 'none' },
    },
    'apps/ui': {
      type: 'react',
      src: ['src/**/*.{ts,tsx}'],
    },
    'apps/ingest': {
      type: 'worker',
      src: ['src/**/*.ts'],
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
    roots: ['apps/ui/src', 'apps/ingest/src'],
  },
});
