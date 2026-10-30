import { useState } from 'react'
import ChatView from './components/ChatView'
import Landing from './components/Landing'
import PatronesLima from './components/PatronesLima'
import { obtenerSessionId } from './lib/session'
import { useTema } from './lib/tema'

type Vista = 'inicio' | 'chat'

// SPA de dos vistas con estado local (sin enrutador): la pantalla de inicio y
// el chat viven montados y se alternan con la clase "hidden", como en el
// prototipo index-lima.html — así el hilo de conversación se conserva.
export default function App() {
  const [vista, setVista] = useState<Vista>('inicio')
  const { tema, alternarTema } = useTema()
  const [sessionId] = useState(obtenerSessionId)

  return (
    <div className="mx-auto flex h-dvh max-w-[720px] flex-col bg-white shadow-2xl shadow-azul/10 transition-colors dark:bg-slate-950 dark:shadow-black/50">
      <PatronesLima />
      <Landing
        visible={vista === 'inicio'}
        tema={tema}
        onAlternarTema={alternarTema}
        onComenzar={() => setVista('chat')}
      />
      <ChatView
        visible={vista === 'chat'}
        tema={tema}
        sessionId={sessionId}
        onAlternarTema={alternarTema}
        onVolver={() => setVista('inicio')}
      />
    </div>
  )
}
