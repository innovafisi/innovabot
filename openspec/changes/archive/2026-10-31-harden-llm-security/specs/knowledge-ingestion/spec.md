# Spec Delta

## Purpose

Endurece la recolección de contenido externo para evitar peticiones del lado del
servidor a destinos no confiables (SSRF) y para verificar que lo descargado es un
PDF real.

## ADDED Requirements

### Requirement: Restricción de descargas a hosts permitidos
El sistema SHALL descargar PDFs solo desde hosts de una allowlist configurable y
SHALL rechazar destinos cuya dirección resuelta sea privada, loopback o
link-local.

#### Scenario: Enlace a un host no permitido
- **WHEN** una página del portal contiene un enlace a un PDF en un host fuera de la allowlist
- **THEN** el enlace se ignora y se registra, sin descargar el recurso

#### Scenario: Enlace a una dirección interna
- **WHEN** un enlace apunta a una IP privada, loopback o link-local
- **THEN** el recurso no se descarga y se registra el descarte

### Requirement: Verificación del tipo de contenido descargado
El sistema SHALL verificar que el contenido descargado sea un PDF real antes de
procesarlo.

#### Scenario: Recurso que no es PDF
- **WHEN** un enlace con extensión `.pdf` devuelve contenido que no es un PDF
- **THEN** el recurso se descarta y se registra, sin intentar extraer texto
