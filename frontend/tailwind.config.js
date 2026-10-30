/** @type {import('tailwindcss').Config} */
// Tokens de identidad FISI + acento de la cerámica Lima (ver index-lima.html
// y el spec web-ui): azul primario, amarillo acento, terracota secundario.
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        azul: {
          DEFAULT: '#003b71',
          oscuro: '#00264a',
        },
        amarillo: {
          DEFAULT: '#ffc72c',
          oscuro: '#e6b125',
          texto: '#c99400', // amarillo legible sobre blanco (tema claro)
        },
        terracota: {
          DEFAULT: '#b3502d',
          claro: '#d98a63', // variante legible sobre fondo oscuro
        },
      },
      keyframes: {
        // Pulso de los puntos del indicador "escribiendo" (ver index-lima.html)
        pulso: {
          '0%, 60%, 100%': { transform: 'translateY(0)', opacity: '0.5' },
          '30%': { transform: 'translateY(-4px)', opacity: '1' },
        },
      },
      animation: {
        pulso: 'pulso 1s infinite ease-in-out',
      },
    },
  },
  plugins: [],
}
