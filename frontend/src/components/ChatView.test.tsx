import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ChatView from './ChatView'

// Tests de la tarea 5.4 (estados de la respuesta) y 5.5 (contador de
// caracteres y header X-Session-ID). fetch va mockeado en todos.

const SESSION_ID = '0f0e8d2a-1a2b-4c3d-8e4f-556677889900'
const URL_API = 'https://backend-innovabot.test'

function montarChat() {
  render(
    <ChatView
      visible
      tema="claro"
      sessionId={SESSION_ID}
      onAlternarTema={() => {}}
      onVolver={() => {}}
    />,
  )
}

async function enviar(texto: string) {
  const usuario = userEvent.setup()
  await usuario.type(screen.getByLabelText('Consulta'), texto)
  await usuario.click(screen.getByRole('button', { name: 'Enviar' }))
}

function simularRespuesta(cuerpo: unknown, estado = 200) {
  vi.mocked(fetch).mockResolvedValue({
    ok: estado < 400,
    status: estado,
    json: async () => cuerpo,
  } as unknown as Response)
}

beforeEach(() => {
  vi.stubEnv('VITE_API_URL', URL_API)
  vi.stubGlobal('fetch', vi.fn())
})

describe('estados de la respuesta (tarea 5.4)', () => {
  it.each([
    {
      estado: 'bloqueada',
      reply: 'Lo sentimos, no podemos responder a ese tipo de consultas.',
    },
    {
      estado: 'limitada',
      reply: 'Has enviado demasiadas consultas. Espera 30 segundos e inténtalo de nuevo.',
    },
    {
      estado: 'sin_resultados',
      reply: 'No encontré información oficial sobre ese tema.',
    },
  ])('muestra el mensaje del backend para estado $estado', async ({ estado, reply }) => {
    simularRespuesta({ reply, citas: [], estado })
    montarChat()
    await enviar('¿Cuándo es la matrícula?')
    await waitFor(() => expect(screen.getByText(reply)).toBeInTheDocument())
  })

  it('muestra el mensaje de límite también cuando llega como HTTP 429', async () => {
    simularRespuesta(
      { reply: 'Límite excedido. Espera 20 segundos.', citas: [], estado: 'limitada' },
      429,
    )
    montarChat()
    await enviar('Otra consulta')
    await waitFor(() =>
      expect(screen.getByText('Límite excedido. Espera 20 segundos.')).toBeInTheDocument(),
    )
  })

  it('muestra un mensaje de respaldo si el backend responde sin texto', async () => {
    simularRespuesta({ reply: '', citas: [], estado: 'sin_resultados' })
    montarChat()
    await enviar('Consulta sin resultados')
    await waitFor(() =>
      expect(
        screen.getByText('No encontré información oficial sobre eso. Prueba a reformular tu consulta o con otro tema de la FISI.'),
      ).toBeInTheDocument(),
    )
  })

  it('muestra un mensaje amigable ante un fallo de red, sin detalles técnicos', async () => {
    vi.mocked(fetch).mockRejectedValue(new TypeError('Failed to fetch'))
    montarChat()
    await enviar('¿Qué carreras ofrece la FISI?')
    await waitFor(() =>
      expect(
        screen.getByText(
          'No pudimos conectar con el servidor. Revisa tu conexión e inténtalo de nuevo en unos instantes.',
        ),
      ).toBeInTheDocument(),
    )
    expect(screen.queryByText(/Failed to fetch/i)).not.toBeInTheDocument()
  })
})

describe('envío de la consulta', () => {
  it('llama a POST /api/chat con el header X-Session-ID y renderiza la respuesta con sus citas', async () => {
    simularRespuesta({
      reply: 'La matrícula empieza en marzo.',
      citas: [{ titulo: 'Calendario académico — Portal FISI', url: 'https://fisi.example/calendario' }],
      estado: 'ok',
    })
    montarChat()
    await enviar('¿Cuándo es la matrícula?')
    await waitFor(() =>
      expect(screen.getByText('La matrícula empieza en marzo.')).toBeInTheDocument(),
    )
    expect(fetch).toHaveBeenCalledWith(
      `${URL_API}/api/chat`,
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ 'X-Session-ID': SESSION_ID }),
        body: JSON.stringify({ query: '¿Cuándo es la matrícula?' }),
      }),
    )
    const enlace = screen.getByText('Calendario académico — Portal FISI')
    expect(enlace).toHaveAttribute('href', 'https://fisi.example/calendario')
  })
})

describe('contador de caracteres (tarea 5.5)', () => {
  it('muestra N/500 y avisa al acercarse al límite', () => {
    montarChat()
    const entrada = screen.getByLabelText('Consulta')
    const contador = screen.getByTestId('contador')

    // Textos largos con fireEvent para no teclear 450 caracteres carácter a carácter.
    fireEvent.change(entrada, { target: { value: 'a'.repeat(100) } })
    expect(contador).toHaveTextContent('100/500')
    expect(contador).not.toHaveClass('font-bold')

    // 450 = 90% del límite: el aviso aparece antes de superar los 500.
    fireEvent.change(entrada, { target: { value: 'a'.repeat(450) } })
    expect(contador).toHaveTextContent('450/500')
    expect(contador).toHaveClass('font-bold')
  })
})
