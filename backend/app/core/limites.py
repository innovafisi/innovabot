"""Límites de uso sin login (spec usage-limits).

Identidad por usuario: user ID de Telegram o session ID web (header
X-Session-ID). Contadores de ventana deslizante EN MEMORIA del proceso:
con un solo contenedor `app` es correcto y barato (design.md §Límites);
si hay réplicas en el futuro, se migra a Redis/tabla sin cambiar la interfaz.
"""

import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable

from app.core.settings import get_settings


class LimiteExcedido(Exception):
    """Señal interna: la consulta excede el límite de frecuencia."""

    def __init__(self, reintento_segundos: int) -> None:
        self.reintento_segundos = reintento_segundos
        super().__init__(f"Límite excedido; reintenta en {reintento_segundos} s")


class LimitesUso:
    """Ventana deslizante por identidad: N/minuto y M/hora, configurables por env."""

    def __init__(
        self,
        por_minuto: int | None = None,
        por_hora: int | None = None,
        max_chars: int | None = None,
        reloj: Callable[[], float] = time.monotonic,
    ) -> None:
        settings = get_settings()
        self.por_minuto = por_minuto if por_minuto is not None else settings.rate_limit_per_minute
        self.por_hora = por_hora if por_hora is not None else settings.rate_limit_per_hour
        self.max_chars = max_chars if max_chars is not None else settings.max_query_chars
        self._reloj = reloj
        self._ventana_minuto: dict[str, deque[float]] = defaultdict(deque)
        self._ventana_hora: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def validar_longitud(self, consulta: str) -> bool:
        """True si la consulta cabe en el límite de caracteres (no se trunca)."""
        return len(consulta) <= self.max_chars

    def verificar(self, identidad: str) -> None:
        """Registra una consulta para `identidad` o lanza LimiteExcedido.

        Debe llamarse SOLO cuando la consulta va a procesarse: las rechazadas
        por longitud no consumen frecuencia (orden de chequeos de design.md).
        """
        ahora = self._reloj()
        with self._lock:
            minuto = self._ventana_minuto[identidad]
            hora = self._ventana_hora[identidad]
            while minuto and ahora - minuto[0] >= 60:
                minuto.popleft()
            while hora and ahora - hora[0] >= 3600:
                hora.popleft()
            if len(minuto) >= self.por_minuto:
                raise LimiteExcedido(int(60 - (ahora - minuto[0])) + 1)
            if len(hora) >= self.por_hora:
                raise LimiteExcedido(int(3600 - (ahora - hora[0])) + 1)
            minuto.append(ahora)
            hora.append(ahora)
