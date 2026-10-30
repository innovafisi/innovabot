import type { Tema } from '../lib/tema'
import BandaLima from './BandaLima'
import Greca from './Greca'
import HuacaLogo from './HuacaLogo'

interface PropiedadesLanding {
  visible: boolean
  tema: Tema
  onAlternarTema: () => void
  onComenzar: () => void
}

// Vista 1: pantalla de inicio con la identidad Lima del prototipo index-lima.html.
export default function Landing({ visible, tema, onAlternarTema, onComenzar }: PropiedadesLanding) {
  return (
    <section
      className={`relative flex-1 flex-col bg-white transition-colors duration-200 dark:bg-slate-950 ${
        visible ? 'flex' : 'hidden'
      }`}
    >
      <BandaLima />

      <button
        type="button"
        onClick={onAlternarTema}
        aria-label="Cambiar tema"
        className="absolute right-4 top-7 flex h-[42px] w-[42px] items-center justify-center rounded-full border-[1.5px] border-slate-200 bg-white text-lg text-slate-800 transition-colors hover:bg-slate-50 active:scale-95 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
      >
        {tema === 'oscuro' ? '☀️' : '🌙'}
      </button>

      <div className="mx-auto flex w-full max-w-[460px] flex-1 flex-col items-center justify-center px-5 py-8 text-center">
        {/* Logo: huaca escalonada con sol, sobre fondo blanco fijo en ambos temas */}
        <div className="mb-5 flex h-[92px] w-[92px] items-center justify-center rounded-3xl border-2 border-slate-200 bg-white shadow-lg shadow-azul/10 dark:border-slate-700 dark:shadow-black/40">
          <HuacaLogo tamaño={56} />
        </div>

        <h1 className="mb-1 text-[2.1rem] tracking-tight text-azul transition-colors dark:text-white md:text-[2.4rem]">
          InnovaBot
        </h1>
        <p className="mb-1.5 font-bold text-amarillo-texto transition-colors dark:text-amarillo">
          Tu asistente de consultas sobre la FISI
        </p>

        <Greca />

        <p className="mb-8 text-[0.98rem] leading-relaxed text-azul transition-colors dark:text-white">
          Resuelve tus dudas sobre la Facultad de Ingeniería de Sistemas e Informática de la UNMSM
          con respuestas basadas en fuentes oficiales, siempre con citas para que verifiques la
          información.
        </p>

        <button
          type="button"
          onClick={onComenzar}
          className="rounded-full bg-amarillo px-[38px] py-[15px] text-base font-bold text-azul-oscuro transition-colors hover:bg-amarillo-oscuro active:scale-[0.97]"
        >
          Comenzar a chatear
        </button>

        <p className="mt-8 text-xs text-slate-400 dark:text-slate-500">
          Facultad de Ingeniería de Sistemas e Informática · UNMSM
        </p>
        <p className="mt-1.5 text-[0.7rem] italic text-terracota dark:text-terracota-claro">
          Diseño inspirado en el arte de la cultura Lima, habitante de la huaca de San Marcos
        </p>
      </div>
    </section>
  )
}
