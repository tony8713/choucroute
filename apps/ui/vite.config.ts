import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const extensions = ['.web.tsx', '.web.ts', '.web.jsx', '.web.js', '.tsx', '.ts', '.jsx', '.js', '.json'];

export default defineConfig({
  plugins: [react()],
  define: {
    global: 'globalThis',
    __DEV__: JSON.stringify(process.env.NODE_ENV !== 'production'),
  },
  resolve: {
    alias: { 'react-native': 'react-native-web' },
    extensions,
  },
  optimizeDeps: {
    include: ['react-native-web', '@stage-labs/kit'],
    esbuildOptions: {
      resolveExtensions: extensions,
      loader: { '.js': 'jsx' },
    },
  },
  server: { port: 5175 },
});
