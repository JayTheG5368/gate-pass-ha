import commonjs from '@rollup/plugin-commonjs';
import { nodeResolve } from '@rollup/plugin-node-resolve';
import terser from '@rollup/plugin-terser';

export default {
  input: 'frontend/src/gate-pass-card.js',
  output: {
    file: 'custom_components/gate_pass/frontend/gate-pass-card.js',
    format: 'es',
    sourcemap: false,
  },
  plugins: [nodeResolve({ browser: true }), commonjs(), terser()],
};

