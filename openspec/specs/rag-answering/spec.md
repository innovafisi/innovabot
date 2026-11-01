# rag-answering Specification

## Purpose
Produce las respuestas del chatbot: reescribe la consulta con el light LM, recupera fragmentos relevantes de PostgreSQL (pgvector), genera la respuesta en español con el LLM principal, la valida contra los fragmentos recuperados y la entrega con citas a las fuentes. Las citas reflejan solo los fragmentos utilizados, las llamadas al LLM principal están acotadas (tokens y timeout) y la validación se hace sobre un contexto acotado.

## Requirements

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

### Requirement: Validación sobre un contexto acotado
El sistema SHALL validar la respuesta generada contra un número acotado de los
fragmentos más relevantes y con cada fragmento truncado a un máximo de
caracteres, de modo que el prompt del validador no crezca sin límite.

#### Scenario: Documentos largos recuperados
- **WHEN** la recuperación devuelve fragmentos largos o numerosos
- **THEN** el prompt de validación usa como máximo los fragmentos más relevantes y trunca cada uno a la longitud máxima, acotando el coste de la validación

#### Scenario: Respuesta respaldada por las fuentes principales
- **WHEN** la respuesta se apoya en los fragmentos más relevantes recuperados
- **THEN** la validación la considera respaldada y se entrega con normalidad
