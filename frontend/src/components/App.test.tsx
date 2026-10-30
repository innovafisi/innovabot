import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'

// Test de la tarea 5.5: la session ID anónima (UUID v4) se genera en la
// primera carga, viaja en el header X-Session-ID y persiste entre recargas
// (re-render/remount con el mismo localStorage). fetch va mockeado.

const URL_API = 'https://backend-innovabot.test'
const REGEX_UUID_V4 =
  /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

function simularRespuestaOk() {
  vi.mocked(fetch).mockImplementation(
    async () =>
      ({
        ok: true,
        status: 200,
        json: async () => ({ reply: 'Respuesta de prueba', citas: [], estado: 'ok' }),
      }) as unknown as Response,
  )
}

async function enviarUnaConsulta() {
  const usuario = userEvent.setup()
  await usuario.click(screen.getByRole('button', { name: 'Comenzar a chatear' }))
  await usuario.type(screen.getByLabelText('Consulta'), 'Hola')
  await usuario.click(screen.getByRole('button', { name: 'Enviar' }))
  await waitFor(() => expect(screen.getByText('Respuesta de prueba')).toBeInTheDocument())
}

function sessionIdEnviada(): string {
  const [, init] = vi.mocked(fetch).mock.calls[0]
  const headers = init?.headers as unknown as Record<string, string>
  return headers['X-Session-ID']
}

beforeEach(() => {
  vi.stubEnv('VITE_API_URL', URL_API)
  vi.stubGlobal('fetch', vi.fn())
  simularRespuestaOk()
})

describe('session ID anónima (tarea 5.5)', () => {
  it('genera un UUID v4, lo envía como X-Session-ID y lo persiste entre recargas', async () => {
    const primera = render(<App />)
    await enviarUnaConsulta()

    const idPrimera = sessionIdEnviada()
    expect(idPrimera).toMatch(REGEX_UUID_V4)
    expect(window.localStorage.getItem('innovabot-session-id')).toBe(idPrimera)

    primera.unmount()
    vi.mocked(fetch).mockClear()

    // "Recarga": nuevo montaje con el mismo localStorage.
    render(<App />)
    await enviarUnaConsulta()

    expect(sessionIdEnviada()).toBe(idPrimera)
  })
})
