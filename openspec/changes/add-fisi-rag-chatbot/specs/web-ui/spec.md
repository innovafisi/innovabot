# Spec Delta

## Purpose

Interfaz de chat web mobile-responsive, de diseño simple con azul como color primario y amarillo como acento (identidad de la FISI), que expone los mismos flujos de respuesta del pipeline RAG desde el navegador.

## ADDED Requirements

### Requirement: Página de chat mobile-responsive
El sistema SHALL servir una página de chat que funcione y se vea correctamente en pantallas de móvil, tablet y escritorio, sin desplazamiento horizontal.

#### Scenario: Acceso desde móvil
- **WHEN** un usuario abre la página desde un teléfono
- **THEN** el chat ocupa el ancho de la pantalla y todos los controles son utilizables sin zoom ni scroll horizontal

#### Scenario: Acceso desde escritorio
- **WHEN** un usuario abre la página desde una pantalla grande
- **THEN** el chat se centra en un ancho máximo legible manteniendo el diseño simple

### Requirement: Identidad visual de la facultad con rasgos de la cultura Lima
La página SHALL usar azul como color primario, amarillo como color de acento y terracota como acento secundario, incorporando rasgos del arte de la cultura Lima — banda de triángulos entrelazados, logotipo de huaca escalonada con sol triangular y greca escalonada — sin perder la identidad FISI.

#### Scenario: Carga de la página
- **WHEN** un usuario carga la página
- **THEN** la interfaz presenta los elementos primarios en azul, los acentos en amarillo, la banda de triángulos entrelazados y el logotipo de huaca escalonada con sol

#### Scenario: Icono del bot visible en ambos temas
- **WHEN** la página se muestra en modo claro o en modo oscuro
- **THEN** el icono del bot se muestra sobre fondo blanco, con la pirámide y el sol visibles en ambos temas, tanto en la vista de inicio como en la cabecera del chat

### Requirement: Pantalla de inicio con presentación del bot
La página SHALL mostrar en una pantalla inicial el nombre del bot, su propósito (consultas sobre la FISI) y un botón para comenzar a chatear; al pulsar el botón, la página pasa a la vista de chat.

#### Scenario: Primera carga de la página
- **WHEN** un usuario carga la página
- **THEN** ve la pantalla de inicio con el nombre del bot, su propósito y el botón para comenzar a chatear

#### Scenario: Iniciar el chat
- **WHEN** el usuario pulsa el botón para comenzar a chatear
- **THEN** la vista cambia a la de chat, con el campo de entrada listo para la primera consulta

### Requirement: Modo claro y oscuro
La página SHALL ofrecer modo claro y oscuro con el modo claro por defecto y un control para alternar entre ambos. En modo claro el fondo será blanco, el título en azul oscuro, el subtítulo en amarillo y la descripción en azul; en modo oscuro el fondo será negro, el título y la descripción en blanco, y el subtítulo se mantiene en amarillo. El botón de comenzar y los acentos de la identidad funcionan en ambos temas, y la vista de chat se adapta a cada tema.

#### Scenario: Primera carga
- **WHEN** un usuario carga la página por primera vez
- **THEN** la interfaz se muestra en modo claro

#### Scenario: Alternar a modo oscuro
- **WHEN** el usuario activa el modo oscuro desde el control
- **THEN** el fondo pasa a negro, el título y la descripción a blanco y el subtítulo permanece en amarillo, en la pantalla de inicio y en el chat

#### Scenario: Preferencia de tema recordada
- **WHEN** el usuario recarga la página después de haber elegido el modo oscuro
- **THEN** la página se muestra directamente en modo oscuro

### Requirement: Intercambio de mensajes con historial en pantalla
La página SHALL permitir al usuario enviar consultas y mostrar las respuestas del pipeline RAG en un hilo de conversación visible, con indicador de espera mientras se genera la respuesta.

#### Scenario: Conversación en pantalla
- **WHEN** el usuario envía una consulta y llega la respuesta
- **THEN** ambos mensajes quedan visibles en el hilo de conversación, con las citas de la respuesta

#### Scenario: Respuesta en curso
- **WHEN** el usuario envía una consulta y la respuesta aún se genera
- **THEN** la página muestra un indicador de espera y mantiene el campo de envío deshabilitado o disponible según el estado

### Requirement: Endpoint de chat del backend
El backend SHALL exponer un endpoint de chat que reciba la consulta del usuario y devuelva la respuesta del pipeline RAG con sus citas, para consumo exclusivo de la página web.

#### Scenario: Consulta válida
- **WHEN** la página envía una consulta legítima al endpoint de chat
- **THEN** recibe la respuesta del pipeline RAG con su texto y citas en un solo resultado

#### Scenario: Consulta bloqueada
- **WHEN** la página envía una consulta que el guardián bloquea
- **THEN** el endpoint devuelve el mensaje estándar de rechazo con el mismo formato de respuesta
