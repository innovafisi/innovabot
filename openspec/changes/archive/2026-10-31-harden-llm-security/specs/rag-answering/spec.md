# Spec Delta

## Purpose

Refuerza el pipeline de respuesta para que las citas sean fieles a los
fragmentos efectivamente usados y para acotar el consumo del LLM principal.

## ADDED Requirements

### Requirement: Citas fieles a los fragmentos utilizados
El sistema SHALL citar únicamente las fuentes de los fragmentos que la respuesta
utilizó efectivamente, de modo que las citas no sugieran un respaldo que no
existe; si no puede determinarse, SHALL degradar al conjunto de fragmentos
recuperados.

#### Scenario: Respuesta que usa parte del contexto
- **WHEN** la recuperación devuelve tres fragmentos y la respuesta se basa solo en uno
- **THEN** la respuesta cita únicamente la fuente del fragmento utilizado

#### Scenario: Fuentes indeterminables
- **WHEN** no se puede determinar qué fragmentos usó la respuesta
- **THEN** se citan todas las fuentes recuperadas (sin perder citas)

### Requirement: Llamadas al LLM principal acotadas
El sistema SHALL acotar cada llamada al LLM principal con un máximo de tokens de
salida y un tiempo límite, configurables, y SHALL responder con un mensaje
estándar ante un timeout o error del servicio.

#### Scenario: Respuesta más larga que el máximo
- **WHEN** la generación alcanza el máximo de tokens de salida
- **THEN** la respuesta se entrega dentro del límite sin bloquear el pipeline

#### Scenario: Timeout del LLM principal
- **WHEN** el LLM principal no responde dentro del tiempo límite
- **THEN** el usuario recibe un mensaje estándar y el error queda registrado sin detalles técnicos
