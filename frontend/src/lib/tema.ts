import { useEffect, useState } from 'react'

// Modo claro/oscuro (tarea 5.3): claro por defecto, toggle en ambas vistas y
// preferencia persistida en localStorage (clave "theme", valores "light"/
// "dark") aplicada como clase "dark" en <html>.

export type Tema = 'claro' | 'oscuro'

const CLAVE_TEMA = 'theme'

function leerTemaGuardado(): Tema {
  try {
    return localStorage.getItem(CLAVE_TEMA) === 'dark' ? 'oscuro' : 'claro'
  } catch {
    return 'claro'
  }
}

export function useTema(): { tema: Tema; alternarTema: () => void } {
  const [tema, setTema] = useState<Tema>(leerTemaGuardado)

  useEffect(() => {
    document.documentElement.classList.toggle('dark', tema === 'oscuro')
    try {
      localStorage.setItem(CLAVE_TEMA, tema === 'oscuro' ? 'dark' : 'light')
    } catch {
      /* sin storage */
    }
  }, [tema])

  return {
    tema,
    alternarTema: () => setTema((actual) => (actual === 'oscuro' ? 'claro' : 'oscuro')),
  }
}
