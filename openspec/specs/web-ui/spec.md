# web-ui Specification

## Purpose
Interfaz de chat web mobile-responsive, de diseño simple con azul como color primario y amarillo como acento (identidad de la FISI), que expone los mismos flujos de respuesta del pipeline RAG desde el navegador. Las URLs de citas solo se renderizan como enlaces si usan http/https.

## Requirements

### Requirement: Saneamiento de las URLs de citas
La página SHALL renderizar una cita como enlace únicamente si su URL usa el
esquema `http` o `https`; cualquier otro esquema SHALL mostrarse como texto sin
enlace.

#### Scenario: Cita con esquema no permitido
- **WHEN** una cita recibida tiene una URL con un esquema distinto de `http`/`https` (p. ej. `javascript:`)
- **THEN** la cita se muestra como texto y no como enlace clicable

#### Scenario: Cita con esquema permitido
- **WHEN** una cita tiene una URL `https://`
- **THEN** se renderiza como enlace que se abre en una pestaña nueva con `rel="noopener noreferrer"`
