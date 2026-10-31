# Spec Delta

## Purpose

Endurece el manejo de la salida del LLM en la web para que las citas solo se
rendericen como enlaces seguros.

## ADDED Requirements

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
