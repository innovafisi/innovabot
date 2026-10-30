// Logotipo: huaca escalonada con sol triangular (cultura Lima).
// Vive sobre fondo blanco fijo en ambos temas, así que sus colores no cambian.
export default function HuacaLogo({ tamaño = 56 }: { tamaño?: number }) {
  return (
    <svg width={tamaño} height={tamaño} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      {/* Sol triangular */}
      <path d="M12 1 L14.4 4.6 L12 8.2 L9.6 4.6 Z" className="fill-terracota" />
      {/* Huaca escalonada */}
      <path
        d="M0 22 h24 v-3.4 h-5 v-5.4 h-5 v-5.4 h-4 v5.4 h-5 v5.4 h-5 Z"
        className="fill-azul"
      />
      {/* Líneas de adobe */}
      <path d="M3 20 h18 M7 14.6 h10" className="stroke-amarillo" strokeWidth="0.9" />
    </svg>
  )
}
