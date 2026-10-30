import { defineConfig } from 'vitest/config'

// Configuración separada de la de Vite: Vitest corre en jsdom y no necesita
// el plugin de React (esbuild transforma el TSX por sí solo).
export default defineConfig({
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
  },
})
