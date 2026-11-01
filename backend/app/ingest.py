"""Alias de entrada de la ingesta: `python -m app.ingest`.

El pipeline de ingesta vive en el paquete `app.ingestion` (con su `__main__.py`).
Este módulo existe para que el comando documentado (`python -m app.ingest`), el
`command` de los compose y el cron de despliegue funcionen tal cual, sin cambiar
la documentación ni los specs. También sigue disponible `python -m app.ingestion`.
"""

from app.ingestion.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
