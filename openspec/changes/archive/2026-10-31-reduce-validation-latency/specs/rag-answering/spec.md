# Spec Delta

## Purpose

Acota el contexto que se entrega a la validación anti-alucinación para reducir
la latencia del pipeline en despliegues CPU-only, sin cambiar el contrato de
respuesta.

## ADDED Requirements

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
