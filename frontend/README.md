# InnovaBot — Frontend web

SPA de React + TypeScript (Vite + Tailwind CSS) para el chatbot RAG de consultas
sobre la Facultad de Ingeniería de Sistemas e Informática (FISI) de la UNMSM.
Es una réplica fiel del prototipo aprobado `index-lima.html` (raíz del repo):
pantalla de inicio con el arte de la cultura Lima y vista de chat con citas a
fuentes oficiales.

## Requisitos

- Node.js 20+ y npm 10+ (desarrollado con Node 24 / npm 11).

## Comandos

```bash
npm install        # instalar dependencias
npm run dev        # servidor de desarrollo (http://localhost:5173)
npm run build      # build de producción en dist/ (tsc -b + vite build)
npm run preview    # servir el build de producción localmente
npm run lint       # ESLint
npm run test       # tests de componentes (Vitest + Testing Library, jsdom)
```

## Configuración: `VITE_API_URL`

La app llama a `POST {VITE_API_URL}/api/chat` con el body `{"query": string}`
y el header `X-Session-ID` (UUID v4 anónima, ver abajo). Respuesta esperada:

```json
{
  "reply": "string",
  "citas": [{ "titulo": "string", "url": "string" }],
  "estado": "ok | bloqueada | sin_resultados | limitada"
}
```

El HTTP 429 por límite de frecuencia llega con el mismo body y estado
`limitada`.

- **Local**: crea un archivo `.env.local` en `frontend/` con la URL pública del
  backend, por ejemplo `VITE_API_URL=https://innovabot.duckdns.org`.
- **Vercel**: define la variable de entorno `VITE_API_URL` en el proyecto
  (Settings → Environment Variables). El frontend se sirve desde Vercel; el
  backend NO sirve los estáticos.

### Modo prototipo (sin backend)

Si `VITE_API_URL` **no** está definida, la app corre en modo prototipo: cada
consulta recibe una respuesta simulada tras ~1 segundo (con una cita de
ejemplo), igual que el prototipo estático. Sirve para demostrar y probar la UI
sin backend.

## Prueba manual de envío/respuesta (tarea 5.2)

Procedimiento documentado para verificar el flujo completo:

1. `npm run dev` y abre `http://localhost:5173` (sin `VITE_API_URL` → modo
   prototipo).
2. Verifica la pantalla de inicio: logo de huaca escalonada con sol, nombre
   "InnovaBot", tagline, greca escalonada, propósito y botón "Comenzar a
   chatear", más la banda de triángulos entrelazados arriba.
3. Pulsa "Comenzar a chatear": la vista cambia al chat, con el campo de entrada
   listo (enfocado) para la primera consulta.
4. Escribe una consulta y envíala: tu mensaje aparece en el hilo (burbuja
   azul), se muestra el indicador de espera de tres puntos (~1 s) y luego la
   respuesta del bot con su cita (borde terracota), abrible en pestaña nueva.
5. Con backend real: define `VITE_API_URL`, reinicia `npm run dev` y repite la
   consulta; la respuesta debe venir del pipeline RAG. Prueba también los
   estados: una consulta bloqueada muestra el mensaje de rechazo; al exceder el
   límite (5/min) aparece el mensaje con el tiempo de espera; una consulta sin
   resultados muestra el mensaje estándar; con el backend caído aparece el
   mensaje amigable de conexión.
6. Verifica el contador `N/500` junto al campo: al pasar de 450 caracteres
   (90% del límite) se resalta en amarillo y negrita.
7. Comprueba que `npm run lint`, `npm run build` y `npm run test` pasan en
   verde.

## Revisión pendiente en viewport móvil (tarea 5.3)

La verificación de la tarea 5.3 exige una revisión con DevTools que queda
pendiente para el equipo:

1. Abre la app (`npm run dev`) en Chrome y activa DevTools → Device Toolbar
   (Ctrl+Shift+M).
2. Elige un teléfono (ej. Pixel 7 / iPhone SE) y comprueba que **no hay scroll
   horizontal** en ninguna de las dos vistas, tampoco con mensajes largos o
   citas con URLs extensas.
3. Alterna claro/oscuro desde el toggle de ambas vistas: los colores siguen los
   tokens (azul `#003b71`, amarillo `#ffc72c`, terracota `#b3502d`), el icono
   del bot se ve sobre fondo blanco en ambos temas (inicio y cabecera del chat)
   y la preferencia persiste al recargar.
4. Repite en una tablet y en escritorio: el contenido se centra con ancho
   máximo de 720 px.

## Detalles de implementación

- **Tema**: claro por defecto; toggle en ambas vistas; preferencia persistida
  en `localStorage` (clave `theme`, valores `light`/`dark`) aplicada como clase
  `dark` en `<html>` antes del primer render (script en `index.html`, sin
  destello).
- **Session ID anónima** (tarea 5.5): UUID v4 generada en la primera carga,
  persistida en `localStorage` (clave `innovabot-session-id`) y enviada como
  header `X-Session-ID` en cada consulta. Borrar el storage reinicia la
  identidad.
- **Estados** (tarea 5.4): la UI muestra el `reply` del backend para
  `bloqueada`, `limitada` (incluye el tiempo de espera) y `sin_resultados`; si
  el backend responde sin texto hay mensajes de respaldo en español, y ante un
  fallo de red se muestra un mensaje amigable sin detalles técnicos.
- **Colores**: solo tokens de `tailwind.config.js` (`azul`, `amarillo`,
  `terracota`) más la paleta neutra de Tailwind (slate/white) para superficies
  y texto; sin colores hardcodeados en componentes.
- **Arquitectura**: dos vistas con estado local, sin enrutador ni librerías de
  estado (KISS). Las vistas viven montadas y se alternan con la clase `hidden`,
  como en el prototipo, para conservar el hilo al volver del inicio.
- **Tests**: Vitest + jsdom + Testing Library con `fetch` mockeado; cubren los
  estados de la respuesta, el header `X-Session-ID`, la persistencia de la
  session ID entre recargas y el aviso del contador de caracteres.

## Estructura

```
src/
  App.tsx                 # Dos vistas con estado local (sin enrutador)
  components/
    Landing.tsx           # Pantalla de inicio
    ChatView.tsx          # Vista de chat (hilo, composer, estados)
    HuacaLogo.tsx         # Logotipo: huaca escalonada con sol
    BandaLima.tsx         # Banda de triángulos entrelazados
    PatronesLima.tsx      # defs SVG compartidas del patrón Lima
    Greca.tsx             # Greca escalonada
    ChatView.test.tsx     # Tests de estados y contador (tareas 5.4/5.5)
    App.test.tsx          # Test de persistencia de session ID (tarea 5.5)
  lib/
    api.ts                # Cliente de POST /api/chat + modo prototipo
    session.ts            # UUID v4 persistida en localStorage
    tema.ts               # Hook de tema claro/oscuro
  test/setup.ts           # Limpieza entre tests (RTL + localStorage)
```
