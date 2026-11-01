# supply-chain-integrity Specification

## Purpose
Asegura la procedencia e integridad del software y los modelos que usa InnovaBot,
y la detección de vulnerabilidades conocidas en sus dependencias.

## Requirements

### Requirement: Dependencias fijadas e íntegras
El proyecto SHALL instalar sus dependencias desde un conjunto fijado y
verificable (lockfile con hashes), de modo que una instalación sea reproducible y
no admita versiones no revisadas.

#### Scenario: Instalación reproducible
- **WHEN** se instala el backend en un entorno limpio desde el lockfile
- **THEN** se obtienen exactamente las versiones fijadas y sus hashes coinciden

### Requirement: Integridad de los modelos descargados
El sistema SHALL fijar la procedencia de los modelos (revisión/hash del modelo de
embeddings y digest del modelo de Ollama) y SHALL usar esas referencias fijas al
descargarlos o ejecutarlos.

#### Scenario: Modelo de embeddings con revisión fija
- **WHEN** se cargan los embeddings
- **THEN** se usa la revisión configurada del modelo, no la última versión por defecto

#### Scenario: Modelo de Ollama por digest
- **WHEN** se prepara el light LM en el ECS
- **THEN** se descarga el digest documentado del modelo

### Requirement: Imágenes de contenedor fijadas por digest
El despliegue SHALL referenciar las imágenes de contenedor por digest
(`@sha256:…`), no por tag mutable.

#### Scenario: Compose de producción con digests
- **WHEN** se inspecciona el compose de producción
- **THEN** todas las imágenes referencian un digest inmutable

### Requirement: Detección de vulnerabilidades
El proyecto SHALL disponer de un mecanismo de escaneo de vulnerabilidades de
dependencias y de generación de SBOM para sus artefactos.

#### Scenario: Escaneo de dependencias
- **WHEN** se ejecuta el escaneo de dependencias
- **THEN** se reportan las vulnerabilidades conocidas de las versiones fijadas
