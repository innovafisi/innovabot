# Spec Delta

## Purpose

Produce las respuestas del chatbot: reescribe la consulta con el light LM, recupera fragmentos relevantes de PostgreSQL (pgvector), genera la respuesta en español con el LLM principal, la valida contra los fragmentos recuperados y la entrega con citas a las fuentes.

## ADDED Requirements

### Requirement: Reescritura de consultas para retrieval
El sistema SHALL reescribir la consulta del usuario con el light LM en una consulta optimizada para búsqueda semántica, preservando el sentido original.

#### Scenario: Pregunta coloquial
- **WHEN** el usuario envía "hasta cuándo puedo matricularme?"
- **THEN** la consulta reescrita usada para retrieval es una forma descriptiva equivalente (por ejemplo, "fechas límite de matrícula FISI")

#### Scenario: Consulta ya óptima
- **WHEN** la consulta original ya es precisa y descriptiva
- **THEN** la reescritura conserva su contenido esencial sin degradarlo

### Requirement: Recuperación semántica de fragmentos
El sistema SHALL recuperar de PostgreSQL (pgvector) los fragmentos más relevantes para la consulta reescrita, en un número configurable y priorizando las FAQs curadas cuando apliquen.

#### Scenario: Consulta con respuesta en FAQs
- **WHEN** la consulta coincide con una FAQ curada
- **THEN** el fragmento de la FAQ aparece entre los recuperados con prioridad

#### Scenario: Consulta sobre documento largo
- **WHEN** la respuesta está en un PDF fragmentado por secciones
- **THEN** se recuperan las secciones relevantes del documento, no el documento completo

### Requirement: Generación de respuesta con el LLM principal
El sistema SHALL generar la respuesta con el LLM principal usando exclusivamente los fragmentos recuperados como contexto, en español y con un tono institucional.

#### Scenario: Respuesta con contexto suficiente
- **WHEN** los fragmentos recuperados contienen la información solicitada
- **THEN** la respuesta responde la consulta en español basándose en ese contenido

#### Scenario: Contexto insuficiente
- **WHEN** los fragmentos recuperados no contienen la información solicitada
- **THEN** la respuesta lo indica en lugar de inventar información

### Requirement: Validación anti-alucinación
El sistema SHALL validar con el light LM que cada afirmación de la respuesta generada esté respaldada por los fragmentos recuperados, antes de entregarla al usuario.

#### Scenario: Respuesta respaldada
- **WHEN** la respuesta generada está respaldada por los fragmentos
- **THEN** se entrega al usuario sin cambios

#### Scenario: Respuesta con afirmaciones no respaldadas
- **WHEN** la validación detecta afirmaciones sin respaldo en los fragmentos
- **THEN** la respuesta no se entrega tal cual: se regenera o se degrada a un mensaje de información no disponible

### Requirement: Citas a las fuentes
El sistema SHALL incluir en cada respuesta las referencias a las fuentes utilizadas, con título y URL de origen de los fragmentos.

#### Scenario: Respuesta basada en una noticia
- **WHEN** la respuesta usa un fragmento de una noticia del portal FISI
- **THEN** la respuesta incluye el título y la URL de esa noticia

### Requirement: Respuesta cuando no hay resultados
El sistema SHALL responder con un mensaje estándar cuando la recuperación no encuentre fragmentos relevantes, sugiriendo consultar el portal oficial.

#### Scenario: Sin fragmentos relevantes
- **WHEN** la recuperación no devuelve fragmentos con relevancia suficiente
- **THEN** el usuario recibe un mensaje indicando que no se encontró información y una referencia al portal oficial

### Requirement: Registro estructurado por consulta
El sistema SHALL registrar por cada consulta recibida un log estructurado con interfaz de origen, categoría (cuando la consulta haya sido clasificada), estado del resultado (ok, bloqueada, sin_resultados, limitada) y latencia, sin almacenar el contenido de la consulta ni datos personales del usuario.

#### Scenario: Consulta exitosa
- **WHEN** una consulta completa el pipeline con respuesta entregada
- **THEN** queda un registro con interfaz, categoría, estado ok y latencia medida

#### Scenario: Conteos diarios
- **WHEN** el equipo consulta los registros de un día
- **THEN** puede obtener conteos por estado, categoría e interfaz a partir de los logs
