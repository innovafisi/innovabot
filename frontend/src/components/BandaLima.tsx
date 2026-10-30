// Banda Lima: triángulos entrelazados sobre franja amarilla con línea
// terracota (franja superior del inicio y bajo la cabecera del chat).
// Requiere <PatronesLima /> montado en el documento.
export default function BandaLima() {
  return (
    <svg
      className="block h-4 w-full shrink-0 border-t-[3px] border-terracota bg-amarillo"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <rect width="100%" height="16" fill="url(#pat-lima)" />
    </svg>
  )
}
