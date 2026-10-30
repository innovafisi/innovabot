# Spec Delta

## Purpose

Aplica límites de uso al chatbot sin requerir login: identifica a cada usuario de forma anónima (user ID de Telegram o session ID web), limita la frecuencia de consultas (5 por minuto, 30 por hora) y la longitud de cada consulta (500 caracteres).

## ADDED Requirements

### Requirement: Identificación del usuario sin login
El sistema SHALL identificar a cada usuario sin requerir login para aplicar los límites: el user ID nativo de Telegram en el bot, y una session ID anónima generada por la web en la primera carga (persistida en localStorage y enviada con cada consulta) en la interfaz web.

#### Scenario: Primera visita a la web
- **WHEN** un usuario carga la página web por primera vez
- **THEN** la página genera una session ID anónima y la envía con cada consulta

#### Scenario: Volver a visitar la web
- **WHEN** el mismo usuario vuelve a la página en el mismo navegador
- **THEN** la session ID persistida se reutiliza, manteniendo sus contadores de límite

#### Scenario: Usuario de Telegram
- **WHEN** un usuario envía consultas por Telegram
- **THEN** los límites se aplican contra su user ID de Telegram

### Requirement: Límite de frecuencia de consultas
El sistema SHALL limitar cada usuario a un máximo de 5 consultas por minuto y 30 por hora, rechazando las consultas que excedan cualquiera de los dos límites.

#### Scenario: Excede el límite por minuto
- **WHEN** un usuario envía su sexta consulta dentro del mismo minuto
- **THEN** la consulta se rechaza con un mensaje estándar indicando cuánto esperar para reintentar, sin ejecutar el pipeline RAG

#### Scenario: Excede el límite por hora
- **WHEN** un usuario envía su consulta número 31 dentro de la misma hora
- **THEN** la consulta se rechaza con un mensaje estándar indicando cuánto esperar para reintentar, sin ejecutar el pipeline RAG

#### Scenario: Uso normal dentro de límites
- **WHEN** un usuario envía consultas respetando ambos límites
- **THEN** ninguna es rechazada por los límites de frecuencia y todas continúan hacia el pipeline de respuesta

### Requirement: Límite de longitud de consulta
El sistema SHALL rechazar consultas de más de 500 caracteres con un mensaje claro pidiendo acortar la consulta, sin truncarlas ni procesarlas.

#### Scenario: Consulta demasiado larga
- **WHEN** un usuario envía una consulta de más de 500 caracteres desde cualquier interfaz
- **THEN** recibe un mensaje indicando el límite de longitud y la consulta no se procesa

#### Scenario: Consulta en el límite exacto
- **WHEN** un usuario envía una consulta de exactamente 500 caracteres
- **THEN** la consulta se procesa con normalidad

### Requirement: Límites configurables
El sistema SHALL permitir configurar los valores de los límites (consultas por minuto, consultas por hora, caracteres por consulta) sin cambios de código, con los valores por defecto en 5, 30 y 500 respectivamente.

#### Scenario: Cambio de configuración
- **WHEN** el equipo ajusta el límite por minuto a 10 en la configuración
- **THEN** el nuevo límite se aplica sin modificar el código del pipeline
