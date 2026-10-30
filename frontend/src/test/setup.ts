import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

// Limpieza entre tests: desmontar componentes, resetear el localStorage y
// restaurar los stubs de fetch / variables de entorno.
afterEach(() => {
  cleanup()
  window.localStorage.clear()
  vi.unstubAllGlobals()
  vi.unstubAllEnvs()
})
