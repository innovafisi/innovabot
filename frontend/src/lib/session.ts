// Session ID anónima (tarea 5.5): UUID v4 generada en la primera carga,
// persistida en localStorage y enviada como header "X-Session-ID" en cada
// consulta. Sin login: el usuario puede borrarla para empezar de cero.

const CLAVE_SESSION = 'innovabot-session-id'

/** UUID v4 (RFC 4122): usa crypto.randomUUID si existe, con respaldo manual. */
export function uuidv4(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (caracter) => {
    const aleatorio = Math.floor(Math.random() * 16)
    const valor = caracter === 'x' ? aleatorio : (aleatorio & 0x3) | 0x8
    return valor.toString(16)
  })
}

/** Devuelve la session ID persistida o genera una nueva en la primera carga. */
export function obtenerSessionId(): string {
  try {
    const guardada = localStorage.getItem(CLAVE_SESSION)
    if (guardada) return guardada
  } catch {
    /* navegador sin storage disponible */
  }
  const id = uuidv4()
  try {
    localStorage.setItem(CLAVE_SESSION, id)
  } catch {
    /* sin storage: la ID solo vive en memoria */
  }
  return id
}
