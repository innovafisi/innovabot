// Definiciones SVG compartidas: patrón de triángulos entrelazados, como los
// peces de la iconografía Lima. Se monta una sola vez en App y la banda lo
// referencia por id.
export default function PatronesLima() {
  return (
    <svg width="0" height="0" className="absolute" aria-hidden="true">
      <defs>
        <pattern id="pat-lima" width="36" height="16" patternUnits="userSpaceOnUse">
          <path d="M0 16 L9 1 L18 16 Z" className="fill-azul" />
          <path d="M18 1 L27 16 L36 1 Z" className="fill-white dark:fill-azul-oscuro" />
        </pattern>
      </defs>
    </svg>
  )
}
