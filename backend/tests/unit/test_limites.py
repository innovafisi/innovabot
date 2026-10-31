"""Tarea 4.6: límites de uso (5/min, 30/hora, 500 chars) por identidad.
Tarea 3.1: límite por IP (LLM10).
Tarea 3.2: memoria de contadores acotada (LLM10).
"""

import pytest

from app.core.limites import LimiteExcedido, LimitesUso


class RelojFalso:
    """Reloj monotónico controlable para simular ventanas de tiempo."""

    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t

    def avanzar(self, segundos: float) -> None:
        self.t += segundos


def test_limite_por_minuto():
    """La 6ª consulta dentro del mismo minuto se rechaza con tiempo de reintento."""
    limites = LimitesUso(reloj=RelojFalso())
    for _ in range(5):
        limites.verificar("telegram:123")
    with pytest.raises(LimiteExcedido) as excinfo:
        limites.verificar("telegram:123")
    assert excinfo.value.reintento_segundos > 0


def test_limite_por_hora():
    """La 31ª consulta dentro de la misma hora se rechaza (ráfagas que respetan el minuto)."""
    reloj = RelojFalso()
    limites = LimitesUso(reloj=reloj)
    for _ in range(6):  # 6 ráfagas de 5 = 30 consultas en la ventana de hora
        for _ in range(5):
            limites.verificar("telegram:123")
        reloj.avanzar(61)  # la ráfaga siguiente no choca con el límite por minuto
    reloj.avanzar(61)  # el minuto está limpio: el rechazo debe venir de la hora
    with pytest.raises(LimiteExcedido) as excinfo:
        limites.verificar("telegram:123")
    # la espera corresponde a la ventana de hora, no a la de minuto
    assert excinfo.value.reintento_segundos > 60


def test_longitud_exacta_y_excedida():
    """500 caracteres pasan; 501 se rechaza sin truncar."""
    limites = LimitesUso()
    assert limites.validar_longitud("a" * 500) is True
    assert limites.validar_longitud("a" * 501) is False


def test_identidades_independientes():
    """Los contadores son por identidad: user ID de Telegram vs session ID web."""
    reloj = RelojFalso()
    limites = LimitesUso(reloj=reloj)
    for _ in range(5):
        limites.verificar("telegram:123")
    with pytest.raises(LimiteExcedido):
        limites.verificar("telegram:123")
    # otra identidad empieza de cero y no está afectada
    limites.verificar("web:uuid-abc")
    limites.verificar("web:uuid-otro")


def test_limite_configurable_por_variable_entorno(monkeypatch):
    """Cambiar RATE_LIMIT_PER_MINUTE a 10 aplica sin tocar código (spec usage-limits)."""
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "10")
    limites = LimitesUso(reloj=RelojFalso())
    assert limites.por_minuto == 10
    for _ in range(10):
        limites.verificar("web:uuid-x")
    with pytest.raises(LimiteExcedido):
        limites.verificar("web:uuid-x")


def test_ventana_deslizante_se_recupera():
    """Pasado el minuto, el usuario vuelve a tener cupo."""
    reloj = RelojFalso()
    limites = LimitesUso(reloj=reloj)
    for _ in range(5):
        limites.verificar("web:uuid-x")
    with pytest.raises(LimiteExcedido):
        limites.verificar("web:uuid-x")
    reloj.avanzar(61)
    limites.verificar("web:uuid-x")  # ya no lanza


# --- Tarea 3.1: límite por IP ---


def test_limite_por_ip():
    """La N+1ª consulta desde la misma IP lanza LimiteExcedido."""
    reloj = RelojFalso()
    limites = LimitesUso(por_minuto_ip=3, reloj=reloj)
    for _ in range(3):
        limites.verificar_ip("1.2.3.4")
    with pytest.raises(LimiteExcedido) as excinfo:
        limites.verificar_ip("1.2.3.4")
    assert excinfo.value.reintento_segundos > 0


def test_ips_distintas_no_interfieren():
    """IPs distintas tienen contadores independientes."""
    reloj = RelojFalso()
    limites = LimitesUso(por_minuto_ip=2, reloj=reloj)
    limites.verificar_ip("1.1.1.1")
    limites.verificar_ip("1.1.1.1")
    # Esta IP ya está al límite, pero otra IP no se ve afectada
    limites.verificar_ip("2.2.2.2")
    limites.verificar_ip("2.2.2.2")


def test_limite_ip_configurable_por_env(monkeypatch):
    """RATE_LIMIT_IP_PER_MINUTE controla el límite por IP."""
    monkeypatch.setenv("RATE_LIMIT_IP_PER_MINUTE", "3")
    limites = LimitesUso(reloj=RelojFalso())
    assert limites.por_minuto_ip == 3
    for _ in range(3):
        limites.verificar_ip("1.2.3.4")
    with pytest.raises(LimiteExcedido):
        limites.verificar_ip("1.2.3.4")


# --- Tarea 3.2: memoria de contadores acotada ---


def test_purga_con_tope_pequeno():
    """Con tope=10, crear 12 identidades mantiene identidades_en_memoria <= 10."""
    reloj = RelojFalso()
    limites = LimitesUso(por_minuto=100, por_hora=100, tope=10, reloj=reloj)
    for i in range(12):
        limites.verificar(f"web:sesion-{i}")
    assert limites.identidades_en_memoria <= 10


def test_purga_inactivas_al_avanzar_reloj():
    """Avanzar el reloj 3601 s + una llamada más purga las inactivas."""
    reloj = RelojFalso()
    limites = LimitesUso(por_minuto=100, por_hora=100, tope=10, reloj=reloj)
    # Llenar hasta el tope con identidades
    for i in range(10):
        limites.verificar(f"web:sesion-{i}")
    assert limites.identidades_en_memoria == 10
    # Avanzar más allá del TTL de 3600 s
    reloj.avanzar(3601)
    # Una nueva llamada dispara la purga de las inactivas (las 10 originales
    # tienen marcas con edad >= 3600 s) y luego añade la nueva
    limites.verificar("web:sesion-nueva")
    # Las 10 originales son inactivas y se purgan; solo queda la nueva
    assert limites.identidades_en_memoria == 1
