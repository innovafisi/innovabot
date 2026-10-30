# Spec Delta

## Purpose

Interfaz de chat vía bot de Telegram (creado con BotFather y atendido por webhook) que expone los mismos flujos de respuesta del pipeline RAG a los usuarios de Telegram.

## ADDED Requirements

### Requirement: Recepción de mensajes vía webhook
El sistema SHALL recibir los mensajes del bot de Telegram a través de un webhook, verificando la autenticidad de cada petición antes de procesarla.

#### Scenario: Mensaje legítimo
- **WHEN** Telegram envía una actualización de mensaje al webhook con la autenticación correcta
- **THEN** la consulta del usuario entra al pipeline de respuesta

#### Scenario: Petición no autenticada
- **WHEN** una petición llega al webhook sin la autenticación esperada de Telegram
- **THEN** la petición se rechaza sin procesarse

### Requirement: Atención solo en chats privados
El bot SHALL responder únicamente a mensajes de chats privados (1:1) e ignorar todo mensaje proveniente de grupos, sin generar respuesta ni ejecutar el pipeline.

#### Scenario: Mensaje en un grupo
- **WHEN** un miembro envía un mensaje en un grupo donde el bot está agregado
- **THEN** el bot no responde y el mensaje no consume pipeline ni límites de uso

#### Scenario: Mensaje privado
- **WHEN** un usuario envía un mensaje al bot en un chat privado
- **THEN** el bot lo procesa con normalidad por el pipeline de respuesta

### Requirement: Respuesta al mensaje del usuario
El sistema SHALL responder en el mismo chat cada consulta legítima con la salida del pipeline RAG, incluyendo las citas a las fuentes cuando la respuesta las tenga.

#### Scenario: Consulta académica por Telegram
- **WHEN** un usuario envía una consulta académica legítima al bot
- **THEN** recibe en el mismo chat la respuesta del pipeline RAG con sus citas

#### Scenario: Consulta bloqueada por el guardián
- **WHEN** un usuario envía una consulta que el guardián bloquea
- **THEN** recibe el mensaje estándar de rechazo en lugar de una respuesta RAG

### Requirement: Comandos del bot
El sistema SHALL atender los comandos /start y /help con mensajes de bienvenida y de temas que el bot puede atender.

#### Scenario: Primer contacto
- **WHEN** un usuario inicia la conversación con /start
- **THEN** recibe un mensaje de bienvenida que presenta al bot y sugiere ejemplos de consultas

#### Scenario: Ayuda
- **WHEN** un usuario envía /help
- **THEN** recibe el listado de temas que el bot puede atender y los comandos disponibles

### Requirement: Manejo de errores ante fallas del pipeline
El sistema SHALL responder con un mensaje amigable en español cuando el pipeline de respuesta falle, sin exponer detalles técnicos al usuario.

#### Scenario: Fallo del LLM principal
- **WHEN** la generación de la respuesta falla por indisponibilidad del servicio
- **THEN** el usuario recibe un mensaje amigable indicando que intente más tarde, y el error queda registrado para el equipo
