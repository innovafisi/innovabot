import { useEffect, useRef, useState, type FormEvent } from 'react'
import { enviarConsulta, textoVisible, type Cita, type RespuestaChat } from '../lib/api'
import type { Tema } from '../lib/tema'
import BandaLima from './BandaLima'
import HuacaLogo from './HuacaLogo'

const MAX_CARACTERES = 500
const UMBRAL_AVISO = 0.9 // aviso del contador al llegar al 90% del límite

// Saneamiento de URLs de citas (cambio harden-llm-security, LLM05): solo se
// renderizan como enlace las URLs con esquema http/https. Cualquier otro
// esquema (javascript:, data:, etc.) se muestra como texto plano sin href.
function esUrlSegura(url: string): boolean {
  return url.startsWith('http://') || url.startsWith('https://')
}

const SALUDO_INICIAL =
  '¡Hola! Soy InnovaBot. Pregúntame lo que quieras sobre la FISI: admisión, planes de estudio, trámites o noticias.'

interface Mensaje {
  id: number
  rol: 'usuario' | 'bot'
  texto: string
  citas: Cita[]
}

interface PropiedadesChat {
  visible: boolean
  tema: Tema
  sessionId: string
  onAlternarTema: () => void
  onVolver: () => void
}

// Vista 2: chat con cabecera azul, hilo de conversación, indicador de espera,
// campo de envío con contador y renderizado de citas (tareas 5.2, 5.4 y 5.5).
export default function ChatView({
  visible,
  tema,
  sessionId,
  onAlternarTema,
  onVolver,
}: PropiedadesChat) {
  const [mensajes, setMensajes] = useState<Mensaje[]>([
    { id: 0, rol: 'bot', texto: SALUDO_INICIAL, citas: [] },
  ])
  const [consulta, setConsulta] = useState('')
  const [pensando, setPensando] = useState(false)
  const hiloRef = useRef<HTMLDivElement>(null)
  const entradaRef = useRef<HTMLInputElement>(null)
  const contadorId = useRef(1)

  // Mantiene el hilo al final y enfoca el campo al entrar a la vista.
  useEffect(() => {
    const hilo = hiloRef.current
    if (hilo) hilo.scrollTop = hilo.scrollHeight
  }, [mensajes, pensando])

  useEffect(() => {
    if (visible) entradaRef.current?.focus()
  }, [visible])

  async function enviar(evento: FormEvent) {
    evento.preventDefault()
    const texto = consulta.trim()
    if (!texto || pensando) return
    setConsulta('')
    setMensajes((actuales) => [
      ...actuales,
      { id: contadorId.current++, rol: 'usuario', texto, citas: [] },
    ])
    setPensando(true)
    const respuesta: RespuestaChat = await enviarConsulta(texto, sessionId)
    setMensajes((actuales) => [
      ...actuales,
      {
        id: contadorId.current++,
        rol: 'bot',
        texto: textoVisible(respuesta),
        citas: respuesta.citas,
      },
    ])
    setPensando(false)
  }

  const avisoLongitud = consulta.length >= MAX_CARACTERES * UMBRAL_AVISO

  return (
    <section className={`min-h-0 flex-1 flex-col ${visible ? 'flex' : 'hidden'}`}>
      {/* Cabecera azul con avatar sobre fondo blanco fijo en ambos temas */}
      <header className="flex items-center gap-3 bg-azul px-4 py-3 text-white transition-colors dark:bg-azul-oscuro">
        <button
          type="button"
          onClick={onVolver}
          aria-label="Volver al inicio"
          className="rounded-lg px-2 py-1 text-xl hover:bg-white/10"
        >
          ←
        </button>
        <div className="flex h-[38px] w-[38px] shrink-0 items-center justify-center rounded-full bg-white">
          <HuacaLogo tamaño={22} />
        </div>
        <div>
          <div className="text-[0.95rem] font-bold">InnovaBot</div>
          <div className="text-xs text-green-300 before:mr-1 before:content-['●']">en línea</div>
        </div>
        <button
          type="button"
          onClick={onAlternarTema}
          aria-label="Cambiar tema"
          className="ml-auto flex h-[38px] w-[38px] items-center justify-center rounded-full border-[1.5px] border-white/25 bg-white/10 text-lg text-white transition-colors hover:bg-white/20 active:scale-95"
        >
          {tema === 'oscuro' ? '☀️' : '🌙'}
        </button>
      </header>

      <BandaLima />

      <div
        ref={hiloRef}
        className="flex flex-1 flex-col gap-3.5 overflow-y-auto bg-slate-50 px-4 py-4 transition-colors dark:bg-slate-900"
      >
        {mensajes.map((mensaje) => (
          <Burbuja key={mensaje.id} mensaje={mensaje} />
        ))}
        {pensando && <IndicadorEspera />}
      </div>

      <form
        onSubmit={enviar}
        className="flex items-center gap-2.5 border-t border-slate-200 bg-white px-3.5 py-3 transition-colors dark:border-slate-700 dark:bg-slate-900"
      >
        <input
          ref={entradaRef}
          type="text"
          value={consulta}
          onChange={(evento) => setConsulta(evento.target.value)}
          maxLength={MAX_CARACTERES}
          placeholder="Escribe tu consulta…"
          autoComplete="off"
          aria-label="Consulta"
          className="flex-1 rounded-full border-[1.5px] border-slate-200 bg-white px-[18px] py-3 text-[0.95rem] text-slate-800 outline-none transition-colors placeholder:text-slate-400 focus:border-azul dark:border-slate-700 dark:bg-slate-950 dark:text-slate-200 dark:focus:border-amarillo"
        />
        <span
          data-testid="contador"
          className={`min-w-[46px] text-right text-[0.72rem] ${
            avisoLongitud
              ? 'font-bold text-amarillo-texto dark:text-amarillo'
              : 'text-slate-400 dark:text-slate-500'
          }`}
        >
          {consulta.length}/{MAX_CARACTERES}
        </span>
        <button
          type="submit"
          disabled={pensando}
          aria-label="Enviar"
          className="flex h-[46px] w-[46px] shrink-0 items-center justify-center rounded-full bg-azul text-base text-white transition-colors hover:bg-azul-oscuro disabled:opacity-60"
        >
          ➤
        </button>
      </form>
    </section>
  )
}

function Burbuja({ mensaje }: { mensaje: Mensaje }) {
  if (mensaje.rol === 'usuario') {
    return (
      <div className="max-w-[82%] self-end rounded-2xl rounded-tr-sm bg-azul px-3.5 py-2.5 text-[0.93rem] leading-relaxed text-white">
        {mensaje.texto}
      </div>
    )
  }
  return (
    <div className="max-w-[82%] self-start rounded-2xl rounded-tl-sm border border-slate-200 border-l-[3px] border-l-amarillo bg-slate-100 px-3.5 py-2.5 text-[0.93rem] leading-relaxed text-slate-800 transition-colors dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200">
      {mensaje.texto}
      {mensaje.citas.length > 0 && (
        <div className="mt-2.5 border-t border-dashed border-slate-200 pt-2 text-xs dark:border-slate-700">
          <strong className="mb-1 block text-azul dark:text-blue-300">Fuentes:</strong>
          {mensaje.citas.map((cita) =>
            // Solo enlaces http/https; el resto como texto plano (LLM05).
            esUrlSegura(cita.url) ? (
              <a
                key={cita.url}
                href={cita.url}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-1 block border-l-[3px] border-terracota pl-2 text-azul hover:underline dark:text-blue-300"
              >
                {cita.titulo}
              </a>
            ) : (
              <span
                key={cita.url}
                className="mt-1 block border-l-[3px] border-terracota pl-2 text-azul dark:text-blue-300"
              >
                {cita.titulo}
              </span>
            ),
          )}
        </div>
      )}
    </div>
  )
}

// Indicador de espera tipo "typing": tres puntos en pulso.
function IndicadorEspera() {
  return (
    <div className="max-w-[82%] self-start rounded-2xl rounded-tl-sm border border-slate-200 border-l-[3px] border-l-amarillo bg-slate-100 px-3.5 py-2.5 dark:border-slate-700 dark:bg-slate-800">
      <span className="inline-flex items-center gap-1" aria-label="Escribiendo">
        <Punto retardo="0s" />
        <Punto retardo="0.15s" />
        <Punto retardo="0.3s" />
      </span>
    </div>
  )
}

function Punto({ retardo }: { retardo: string }) {
  return (
    <span
      className="h-[7px] w-[7px] animate-pulso rounded-full bg-slate-400 dark:bg-slate-500"
      style={{ animationDelay: retardo }}
    />
  )
}
