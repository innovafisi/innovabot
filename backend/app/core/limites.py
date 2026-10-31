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

# Tope de identidades en memoria: evita que miles de session IDs / IPs
# distintas hagan crecer la memoria sin techo (LLM10).
TOPE_IDENTIDADES = 10_000


class LimiteExcedido(Exception):
    """Señal interna: la consulta excede el límite de frecuencia."""

    def __init__(self, reintento_segundos: int) -> None:
        self.reintento_segundos = reintento_segundos
        super().__init__(f"Límite excedido; reintenta en {reintento_segundos} s")


class LimitesUso:
    """Ventana deslizante por identidad: N/minuto y M/hora, configurables por env.

    También soporta límite por IP (por_minuto_ip) para la interfaz web.
    El límite por IP vive en la interfaz web y NO en el orquestador porque
    las peticiones de Telegram llegan desde las IPs de los servidores de
    Telegram (compartidas por todos los usuarios); aplicar límite por IP
    ahí bloquearía a todos colectivamente.
    """

    def __init__(
        self,
        por_minuto: int | None = None,
        por_hora: int | None = None,
        max_chars: int | None = None,
        por_minuto_ip: int | None = None,
        tope: int = TOPE_IDENTIDADES,
        reloj: Callable[[], float] = time.monotonic,
    ) -> None:
        settings = get_settings()
        self.por_minuto = por_minuto if por_minuto is not None else settings.rate_limit_per_minute
        self.por_hora = por_hora if por_hora is not None else settings.rate_limit_per_hour
        self.max_chars = max_chars if max_chars is not None else settings.max_query_chars
        self.por_minuto_ip = (
            por_minuto_ip if por_minuto_ip is not None else settings.rate_limit_ip_per_minute
        )
        self.tope = tope
        self._reloj = reloj
        self._ventana_minuto: dict[str, deque[float]] = defaultdict(deque)
        self._ventana_hora: dict[str, deque[float]] = defaultdict(deque)
        self._ventana_ip: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    @property
    def identidades_en_memoria(self) -> int:
        """Número de identidades rastreadas (sin lock: solo len de dicts)."""
        return max(
            len(self._ventana_minuto),
            len(self._ventana_hora),
            len(self._ventana_ip),
        )

    def _purgar(self, ahora: float) -> None:
        """Si algún dict supera el tope, elimina inactivas y luego las más antiguas.

        Se llama con el lock ya tomado; debe ser barato (no-op bajo el tope).
        """
        for ventana in (self._ventana_minuto, self._ventana_hora, self._ventana_ip):
            if len(ventana) < self.tope:
                continue
            # Primero eliminar entradas inactivas (deque vacía o última marca
            # con edad >= 3600 s)
            inactivas = [
                k for k, v in ventana.items() if not v or ahora - v[-1] >= 3600
            ]
            for k in inactivas:
                del ventana[k]
            # Si sigue sobre el tope, eliminar las más antiguas (orden de inserción)
            if len(ventana) >= self.tope:
                exceso = len(ventana) - self.tope + 1
                for k in list(ventana.keys())[:exceso]:
                    del ventana[k]

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
            self._purgar(ahora)
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

    def verificar_ip(self, ip: str) -> None:
        """Registra una consulta para la IP o lanza LimiteExcedido.

        Ventana deslizante de 60 s, independiente de los contadores por
        identidad. Solo aplica a la interfaz web (ver comentario de clase).
        """
        ahora = self._reloj()
        with self._lock:
            self._purgar(ahora)
            marcas = self._ventana_ip[ip]
            while marcas and ahora - marcas[0] >= 60:
                marcas.popleft()
            if len(marcas) >= self.por_minuto_ip:
                raise LimiteExcedido(int(60 - (ahora - marcas[0])) + 1)
            marcas.append(ahora)
