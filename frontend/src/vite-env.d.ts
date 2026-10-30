/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** URL base del backend (ej. https://innovabot.duckdns.org). Sin ella, la app corre en modo prototipo. */
  readonly VITE_API_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
