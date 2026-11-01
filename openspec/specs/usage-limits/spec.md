# usage-limits Specification

## Purpose
Aplica límites de uso al chatbot sin requerir login: identifica a cada usuario (user ID de Telegram o session ID web), limita la frecuencia de consultas (5 por minuto, 30 por hora) y la longitud de cada consulta (500 caracteres). Se aplica además un límite por dirección IP en la web y la memoria de los contadores está acotada.

## Requirements

### Requirement: Límite adicional por dirección IP
El sistema SHALL aplicar, además del límite por usuario, un límite de frecuencia
por dirección IP de origen, de modo que rotar el identificador de sesión desde
una misma IP no permita superar el cupo.

#### Scenario: Rotación de session ID
- **WHEN** un cliente envía consultas desde la misma IP cambiando el `X-Session-ID` en cada una hasta superar el límite por IP
- **THEN** las consultas por encima del límite por IP se rechazan con el mensaje estándar de límite

#### Scenario: Uso normal desde varias IP
- **WHEN** varios usuarios consultan desde IPs distintas dentro de sus límites individuales
- **THEN** ninguno es rechazado por el límite por IP

### Requirement: Memoria de contadores acotada
El sistema SHALL acotar la memoria usada por los contadores de límites: las
identidades inactivas SHALL purgarse y el número de identidades en memoria SHALL
tener un tope.

#### Scenario: Muchas identidades distintas
- **WHEN** llegan consultas con un gran número de identidades distintas
- **THEN** la memoria de contadores permanece acotada (se purgan las inactivas y se descartan las más antiguas al superar el tope)
