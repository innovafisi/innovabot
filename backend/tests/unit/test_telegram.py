"""Tests del bot de Telegram (grupo 6): webhook, comandos, fallos y filtro de alcance.
Tarea 4.1: webhook sin token en la URL (LLM02).
Tarea 4.2: redacción de errores (LLM02).
Tarea 4.3: anti-replay de updates (LLM10).

Mock de la API de Telegram (cliente falso) y stub del pipeline; los casos de
límite usan el orquestador REAL con clientes falsos, como en test_orquestador.
"""

import itertools
import json
import logging

from fastapi.testclient import TestClient

from app.core.limites import LimitesUso
from app.core.modelos import Cita, Respuesta
from app.interfaces.telegram import AYUDA, BIENVENIDA, MENSAJE_ERROR
from app.main import crear_app
from app.rag.orquestador import Orquestador
from tests.unit.fakes import (
    FakeAlmacen,
    FakeEmbeddings,
    FakeLightLM,
    FakeLLMPrincipal,
)

TOKEN = "123456:test-token"  # dummy de conftest.py, nunca el real
SECRET = "secreto-test"  # dummy de conftest.py

# Contador global para generar update_ids únicos por llamada
_update_id_counter = itertools.count(1)


class TelegramFalso:
    """Mock de la API de Telegram: registra los mensajes enviados."""

    def __init__(self) -> None:
        self.enviados: list[tuple[int, str]] = []

    def enviar_mensaje(self, chat_id: int, texto: str) -> None:
        self.enviados.append((chat_id, texto))


class PipelineStub:
    def __init__(self, respuesta: Respuesta | None = None, error: Exception | None = None):
        self.respuesta = respuesta or Respuesta(reply="ok", estado="ok")
        self.error = error
        self.llamadas: list[tuple[str, str, str]] = []

    def procesar(self, consulta: str, identidad: str, interfaz: str) -> Respuesta:
        self.llamadas.append((consulta, identidad, interfaz))
        if self.error:
            raise self.error
        return self.respuesta


def update_privado(texto: str, chat_id: int = 100, user_id: int = 200) -> dict:
    return {
        "update_id": next(_update_id_counter),
        "message": {
            "message_id": 10,
            "chat": {"id": chat_id, "type": "private"},
            "from": {"id": user_id, "is_bot": False, "first_name": "Test"},
            "text": texto,
        },
    }


def update_grupo(texto: str, chat_id: int = -100) -> dict:
    return {
        "update_id": next(_update_id_counter),
        "message": {
            "message_id": 11,
            "chat": {"id": chat_id, "type": "group"},
            "from": {"id": 200, "is_bot": False, "first_name": "Test"},
            "text": texto,
        },
    }


def cliente_api(pipeline, telegram: TelegramFalso) -> TestClient:
    return TestClient(crear_app(pipeline=pipeline, cliente_telegram=telegram))


def post_update(cliente: TestClient, update: dict, secret: str = SECRET):
    return cliente.post(
        "/telegram/webhook",
        json=update,
        headers={"X-Telegram-Bot-Api-Secret-Token": secret},
    )


def test_webhook_autenticado_se_procesa():
    """Tarea 6.1: una petición autenticada se procesa (200 + una respuesta)."""
    telegram = TelegramFalso()
    stub = PipelineStub(Respuesta(reply="La matrícula es en marzo.", estado="ok"))
    cliente = cliente_api(stub, telegram)
    respuesta = post_update(cliente, update_privado("¿cuándo me matriculo?"))
    assert respuesta.status_code == 200
    assert respuesta.json() == {"ok": True}
    # Exactamente una respuesta, al chat de origen, con identidad telegram:<user_id>
    assert stub.llamadas == [("¿cuándo me matriculo?", "telegram:200", "telegram")]
    assert telegram.enviados == [(100, "La matrícula es en marzo.")]


def test_webhook_sin_secret_rechazado_401():
    """Tarea 6.1: sin el secret token de Telegram la petición se rechaza 401."""
    telegram = TelegramFalso()
    stub = PipelineStub()
    cliente = cliente_api(stub, telegram)
    respuesta = post_update(cliente, update_privado("hola"), secret="secreto-equivocado")
    assert respuesta.status_code == 401
    assert stub.llamadas == []
    assert telegram.enviados == []


def test_ruta_con_token_da_404():
    """Tarea 4.1: la ruta con token (/telegram/webhook/{token}) ya no existe → 404."""
    telegram = TelegramFalso()
    stub = PipelineStub()
    cliente = cliente_api(stub, telegram)
    respuesta = cliente.post(
        f"/telegram/webhook/{TOKEN}",
        json=update_privado("hola"),
        headers={"X-Telegram-Bot-Api-Secret-Token": SECRET},
    )
    assert respuesta.status_code == 404


def test_respuesta_con_citas_en_el_mismo_chat():
    """Tarea 6.2: la respuesta llega al chat de origen con sus citas."""
    telegram = TelegramFalso()
    stub = PipelineStub(
        Respuesta(
            reply="La matrícula es en marzo.",
            citas=[Cita(titulo="Calendario FISI", url="https://sistemas.unmsm.edu.pe/x")],
            estado="ok",
        )
    )
    cliente = cliente_api(stub, telegram)
    post_update(cliente, update_privado("consulta"))
    chat_id, texto = telegram.enviados[0]
    assert chat_id == 100
    assert "La matrícula es en marzo." in texto
    assert "Fuentes:" in texto
    assert "Calendario FISI: https://sistemas.unmsm.edu.pe/x" in texto


def _orquestador_real() -> tuple[Orquestador, TelegramFalso, TestClient]:
    """Webhook cableado al orquestador REAL (clientes falsos) para límites."""
    orquestador = Orquestador(
        limites=LimitesUso(por_minuto=5, por_hora=30, max_chars=500),
        cliente_light=FakeLightLM(
            *[{"safe": True, "category": "tramites", "rewritten_query": "matrícula"}] * 10
        ),
        cliente_llm=FakeLLMPrincipal(),
        cliente_embeddings=FakeEmbeddings(),
        almacen=FakeAlmacen([]),
    )
    telegram = TelegramFalso()
    return orquestador, telegram, cliente_api(orquestador, telegram)


def test_limite_por_minuto_mensaje_de_limite():
    """Tarea 6.2: la 6ª consulta en un minuto recibe el mensaje de límite."""
    _orq, telegram, cliente = _orquestador_real()
    for _ in range(5):
        post_update(cliente, update_privado("consulta"))
    post_update(cliente, update_privado("consulta"))
    assert len(telegram.enviados) == 6
    texto_limite = telegram.enviados[-1][1]
    assert "límite" in texto_limite


def test_consulta_demasiado_larga_aviso_de_acortar():
    """Tarea 6.2: una consulta de >500 caracteres recibe el aviso de acortar."""
    _orq, telegram, cliente = _orquestador_real()
    post_update(cliente, update_privado("a" * 501))
    assert len(telegram.enviados) == 1
    assert "500 caracteres" in telegram.enviados[0][1]


def test_start_y_help_responden_sin_pasar_por_el_pipeline():
    """Tarea 6.3: /start y /help responden su mensaje y NO entran al pipeline."""
    telegram = TelegramFalso()
    stub = PipelineStub()
    cliente = cliente_api(stub, telegram)
    post_update(cliente, update_privado("/start"))
    post_update(cliente, update_privado("/help"))
    assert telegram.enviados == [(100, BIENVENIDA), (100, AYUDA)]
    assert stub.llamadas == []  # los comandos no consumen pipeline


def test_fallo_del_pipeline_mensaje_amigable_y_error_logueado(caplog):
    """Tarea 6.4: ante una excepción del pipeline, mensaje amigable + log del error."""
    caplog.set_level(logging.ERROR, logger="innovabot")
    telegram = TelegramFalso()
    stub = PipelineStub(error=RuntimeError("MaaS caído"))
    cliente = cliente_api(stub, telegram)
    respuesta = post_update(cliente, update_privado("hola"))
    assert respuesta.status_code == 200  # Telegram igual recibe 200
    assert telegram.enviados == [(100, MENSAJE_ERROR)]
    errores = [r for r in caplog.records if r.levelname == "ERROR" and r.name == "innovabot"]
    assert len(errores) == 1
    assert "Fallo del pipeline" in errores[0].getMessage()


def test_update_de_grupo_ignorado_sin_consumir_nada():
    """Tarea 6.5: un update de grupo no genera respuesta ni consume pipeline ni límites."""
    telegram = TelegramFalso()
    stub = PipelineStub()
    cliente = cliente_api(stub, telegram)
    post_update(cliente, update_grupo("hola"))
    assert telegram.enviados == []
    assert stub.llamadas == []


def test_grupo_no_consume_rate_limit():
    """Tarea 6.5: 10 mensajes de grupo no consumen el cupo del usuario privado."""
    _orq, telegram, cliente = _orquestador_real()
    for _ in range(10):
        post_update(cliente, update_grupo("spam de grupo"))
    assert telegram.enviados == []
    # El usuario privado conserva su cupo completo de 5 consultas/minuto
    for _ in range(5):
        post_update(cliente, update_privado("consulta"))
    assert len(telegram.enviados) == 5
    assert all("límite" not in texto for _, texto in telegram.enviados)


def test_update_sin_texto_se_descarta():
    """Updates sin mensaje o sin texto (editados, canales) se descartan."""
    telegram = TelegramFalso()
    stub = PipelineStub()
    cliente = cliente_api(stub, telegram)
    post_update(cliente, {"update_id": next(_update_id_counter)})
    assert telegram.enviados == []
    assert stub.llamadas == []


def test_formato_de_log_por_consulta_telegram(caplog):
    """La interfaz telegram también deja el log estructurado del orquestador."""
    caplog.set_level(logging.INFO, logger="innovabot.consultas")
    _orq, _telegram, cliente = _orquestador_real()
    post_update(cliente, update_privado("consulta legítima"))
    registros = [
        json.loads(r.getMessage())
        for r in caplog.records
        if r.name == "innovabot.consultas"
    ]
    assert len(registros) == 1
    assert registros[0]["interfaz"] == "telegram"
    assert registros[0]["estado"] == "sin_resultados"


# --- Tarea 4.3: anti-replay de updates ---


def test_anti_replay_mismo_update_procesado_una_vez():
    """Mismo update posteado 2 veces → el stub procesa 1 vez y Telegram recibe 1 sola respuesta."""
    telegram = TelegramFalso()
    stub = PipelineStub(Respuesta(reply="ok", estado="ok"))
    cliente = cliente_api(stub, telegram)
    update = update_privado("hola")
    # Primera petición: se procesa
    resp1 = post_update(cliente, update)
    assert resp1.status_code == 200
    assert resp1.json() == {"ok": True}
    # Segunda petición con el mismo update_id: ya visto, se responde ok sin reprocesar
    resp2 = post_update(cliente, update)
    assert resp2.status_code == 200
    assert resp2.json() == {"ok": True}
    # El pipeline solo se llamó una vez
    assert len(stub.llamadas) == 1
    # Telegram solo recibió una respuesta
    assert len(telegram.enviados) == 1


# --- Tarea 4.2: redacción de errores (LLM02) ---


def test_redaccion_error_no_filtra_secreto(caplog):
    """Pipeline que lanza con credenciales en el mensaje → el log NO contiene el secreto."""
    caplog.set_level(logging.ERROR, logger="innovabot")
    telegram = TelegramFalso()
    dsn = "postgresql://root:secreto@192.168.0.168/db"
    stub = PipelineStub(error=RuntimeError(dsn))
    cliente = cliente_api(stub, telegram)
    respuesta = post_update(cliente, update_privado("hola"))
    assert respuesta.status_code == 200
    assert telegram.enviados == [(100, MENSAJE_ERROR)]
    # Verificar que el log NO contiene "secreto" ni "postgresql://"
    for registro in caplog.records:
        if registro.name == "innovabot" and registro.levelname == "ERROR":
            msg = registro.getMessage()
            assert "secreto" not in msg
            assert "postgresql://" not in msg
