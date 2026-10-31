# Spec Delta

## Purpose

Refuerza la autenticación del webhook de Telegram para no exponer el token del
bot en la URL y evita el reprocesamiento de updates repetidos.

## ADDED Requirements

### Requirement: Autenticación del webhook sin exponer el token
El sistema SHALL autenticar las peticiones del webhook mediante el header secreto
de Telegram, y la URL del webhook NO SHALL contener el token del bot (ni ser
registrada en los access logs junto con datos sensibles).

#### Scenario: URL del webhook sin token
- **WHEN** se registra y consulta la configuración del webhook
- **THEN** la URL no incluye el token del bot y la autenticidad se valida por el header secreto

#### Scenario: Petición con secreto inválido
- **WHEN** llega una petición al webhook sin el secreto correcto
- **THEN** se rechaza sin procesarse

### Requirement: Rechazo de updates repetidos
El sistema SHALL ignorar los updates de Telegram ya procesados (mismo
`update_id`) dentro de una ventana reciente, para evitar reprocesar una consulta.

#### Scenario: Reintento del mismo update
- **WHEN** Telegram reenvía un update ya procesado
- **THEN** el sistema no genera una segunda respuesta ni consume límites nuevamente
