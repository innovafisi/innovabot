// Cliente de la API de chat del backend (tareas 5.2 y 5.4).
// Contrato: POST {VITE_API_URL}/api/chat con body {"query": string} y header
// "X-Session-ID"; respuesta {reply, citas: [{titulo, url}], estado} — el HTTP
// 429 por límite excedido llega con el mismo body y estado "limitada".

export interface Cita {
  titulo: string
  url: string
}

/** Estados del contrato, más "error", exclusivo del frontend (fallo de red). */
export type EstadoRespuesta = 'ok' | 'bloqueada' | 'sin_resultados' | 'limitada' | 'error'

export interface RespuestaChat {
  reply: string
  citas: Cita[]
  estado: EstadoRespuesta
}

/** Mensaje amigable ante fallo de red, sin detalles técnicos. */
export const MENSAJE_ERROR_RED =
  'No pudimos conectar con el servidor. Revisa tu conexión e inténtalo de nuevo en unos instantes.'

/** Mensajes de respaldo por estado, por si el backend responde sin texto. */
const MENSAJES_RESPALDO: Record<EstadoRespuesta, string> = {
  ok: 'Lo sentimos, ocurrió un problema al generar la respuesta. Inténtalo de nuevo.',
  bloqueada:
    'Lo sentimos, no podemos responder a ese tipo de consultas. InnovaBot solo atiende dudas sobre la FISI.',
  limitada:
    'Has enviado demasiadas consultas en poco tiempo. Espera un momento antes de volver a intentar.',
  sin_resultados:
    'No encontré información oficial sobre eso. Prueba a reformular tu consulta o con otro tema de la FISI.',
  error: MENSAJE_ERROR_RED,
}

/** Texto a mostrar al usuario: el reply del backend o el respaldo del estado. */
export function textoVisible(respuesta: RespuestaChat): string {
  return respuesta.reply.trim() || MENSAJES_RESPALDO[respuesta.estado]
}

const ESTADOS_BACKEND = ['ok', 'bloqueada', 'sin_resultados', 'limitada'] as const
type EstadoBackend = (typeof ESTADOS_BACKEND)[number]

function esEstadoBackend(valor: unknown): valor is EstadoBackend {
  return typeof valor === 'string' && (ESTADOS_BACKEND as readonly string[]).includes(valor)
}

const RETARDO_PROTOTIPO_MS = 1100

// Modo prototipo (sin VITE_API_URL): respuesta simulada tras ~1 s, como en el
// prototipo estático index-lima.html, para demostrar la UI sin backend.
async function respuestaPrototipo(): Promise<RespuestaChat> {
  await new Promise((resolver) => setTimeout(resolver, RETARDO_PROTOTIPO_MS))
  return {
    reply:
      'Esta es una respuesta de ejemplo del prototipo. En producción, ' +
      'InnovaBot responderá con información verificada de la FISI y ' +
      'citará sus fuentes como se muestra abajo.',
    citas: [
      {
        titulo: 'Noticia de ejemplo — Portal FISI',
        url: 'https://sistemas.unmsm.edu.pe/site/index.php',
      },
    ],
    estado: 'ok',
  }
}

/** Envía una consulta al backend con la session ID como identidad anónima. */
export async function enviarConsulta(query: string, sessionId: string): Promise<RespuestaChat> {
  const baseUrl = import.meta.env.VITE_API_URL
  if (!baseUrl) return respuestaPrototipo()
  try {
    const res = await fetch(`${baseUrl}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Session-ID': sessionId },
      body: JSON.stringify({ query }),
    })
    // El 429 del límite llega con el mismo formato {reply, citas, estado}.
    const data = (await res.json()) as Partial<RespuestaChat>
    return {
      reply: typeof data.reply === 'string' ? data.reply : '',
      citas: Array.isArray(data.citas) ? data.citas : [],
      estado: esEstadoBackend(data.estado) ? data.estado : 'error',
    }
  } catch {
    return { reply: MENSAJE_ERROR_RED, citas: [], estado: 'error' }
  }
}
