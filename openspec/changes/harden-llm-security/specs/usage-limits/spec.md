# Spec Delta

## Purpose

Refuerza los límites de uso para evitar el consumo no acotado del LLM: añade un
límite por dirección IP que no depende de una identidad controlada por el
cliente, y acota la memoria de los contadores.

## ADDED Requirements

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
