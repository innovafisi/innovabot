# Spec Delta

## Purpose

Recopila contenido del portal FISI (noticias), PDFs del portal, FAQs curadas y portal central UNMSM, y lo indexa con embeddings en PostgreSQL (pgvector) para que el pipeline RAG pueda recuperarlo con metadata de fuente y fecha.

## ADDED Requirements

### Requirement: Recolección de noticias del portal FISI
El sistema SHALL extraer periódicamente las noticias publicadas en sistemas.unmsm.edu.pe, incluyendo título, contenido, fecha de publicación y URL.

#### Scenario: Primera recolección
- **WHEN** el pipeline de ingesta se ejecuta por primera vez contra el portal FISI
- **THEN** todas las noticias visibles quedan registradas con título, contenido, fecha y URL

#### Scenario: Recolección incremental
- **WHEN** el pipeline se ejecuta de nuevo y hay noticias nuevas en el portal
- **THEN** solo se ingieren las noticias no registradas previamente

### Requirement: Ingesta de PDFs del portal
El sistema SHALL descargar los PDFs publicados en el portal FISI (planes de estudio, reglamentos, directivas), extraer su texto y dividirlo en fragmentos que preserven secciones y jerarquía del documento.

#### Scenario: PDF con plan de estudios
- **WHEN** se ingiere un PDF de plan de estudios
- **THEN** su texto queda fragmentado por secciones (cursos, requisitos, mallas) sin perder la estructura del documento

#### Scenario: PDF ilegible o corrupto
- **WHEN** se intenta ingerir un PDF del que no se puede extraer texto
- **THEN** el pipeline registra el error con la URL del documento y continúa con los demás archivos

### Requirement: Ingesta de FAQs curadas
El sistema SHALL cargar las preguntas y respuestas oficiales mantenidas manualmente por el equipo, tratándolas como fragmentos de máxima prioridad con su propia metadata de fuente.

#### Scenario: Actualización del archivo de FAQs
- **WHEN** el equipo agrega o modifica entradas en el archivo de FAQs curadas
- **THEN** la siguiente ejecución de ingesta refleja los cambios sin duplicar las entradas existentes

### Requirement: Ingesta de contenido del portal central UNMSM
El sistema SHALL recopilar el contenido relevante del portal unmsm.edu.pe (procesos generales, calendarios, bienestar) delimitado a un conjunto de secciones configurables.

#### Scenario: Sección configurada
- **WHEN** una sección del portal central está incluida en la configuración de ingesta
- **THEN** sus páginas se ingieren con su URL y fecha de consulta

### Requirement: Indexación vectorial con metadata
El sistema SHALL generar embeddings para cada fragmento y indexarlo en PostgreSQL (pgvector) con metadata obligatoria: tipo de fuente, URL de origen, título y fecha.

#### Scenario: Fragmento indexado
- **WHEN** un fragmento completa su procesamiento
- **THEN** queda consultable en PostgreSQL (pgvector) con búsqueda semántica y metadata filtrable

#### Scenario: Metadata incompleta
- **WHEN** un fragmento no puede determinar su URL o tipo de fuente
- **THEN** el pipeline lo marca como inválido y no lo indexa

### Requirement: Deduplicación y actualización de contenido
El sistema SHALL evitar duplicados en re-ingestas: contenido idéntico ya indexado no se vuelve a insertar, y una versión actualizada de un documento reemplaza a la obsoleta.

#### Scenario: Re-ingesta sin cambios
- **WHEN** se ejecuta la ingesta y ninguna fuente tiene contenido nuevo
- **THEN** el índice queda idéntico, sin fragmentos duplicados

#### Scenario: Documento actualizado
- **WHEN** un PDF o noticia cambia en su fuente y se re-ingiere
- **THEN** la versión anterior queda reemplazada por la nueva en el índice
