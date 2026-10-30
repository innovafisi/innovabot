"""Orquestador del pipeline de respuesta (design.md §Pipeline).

Única pieza por la que pasan ambas interfaces (web y Telegram). Aplica los
chequeos del más barato al más caro — longitud → rate limit → regex → light
LM → retrieval → LLM principal → validación — y deja el log estructurado por
cada consulta recibida (spec rag-answering).
"""

import time

from app.core.clientes import (
    AlmacenVectorial,
    ClienteEmbeddings,
    ClienteLightLM,
    ClienteLLMPrincipal,
)
from app.core.limites import LimiteExcedido, LimitesUso
from app.core.logs import registrar_bloqueo, registrar_consulta
from app.core.modelos import Cita, Respuesta
from app.core.settings import get_settings
from app.guard import light_lm_guard, mensajes, regex_guard
from app.rag import generacion, retrieval, validacion


def armar_citas(fragmentos) -> list[Cita]:
    """Citas de los fragmentos usados, deduplicadas por URL (un PDF aporta una cita)."""
    citas: list[Cita] = []
    vistas: set[str] = set()
    for f in fragmentos:
        if f.url not in vistas:
            vistas.add(f.url)
            citas.append(Cita(titulo=f.titulo, url=f.url))
    return citas


class Orquestador:
    """Pipeline de respuesta; dependencias inyectadas para testabilidad."""

    def __init__(
        self,
        limites: LimitesUso,
        cliente_light: ClienteLightLM,
        cliente_llm: ClienteLLMPrincipal,
        cliente_embeddings: ClienteEmbeddings,
        almacen: AlmacenVectorial,
        top_k: int | None = None,
        min_similitud: float | None = None,
    ) -> None:
        settings = get_settings()
        self.limites = limites
        self.cliente_light = cliente_light
        self.cliente_llm = cliente_llm
        self.cliente_embeddings = cliente_embeddings
        self.almacen = almacen
        self.top_k = top_k if top_k is not None else settings.retrieval_top_k
        self.min_similitud = (
            min_similitud if min_similitud is not None else settings.retrieval_min_similitud
        )

    def procesar(self, consulta: str, identidad: str, interfaz: str) -> Respuesta:
        """Procesa una consulta de principio a fin y devuelve la respuesta con citas."""
        inicio = time.monotonic()
        # 1. Longitud (chequeo más barato; no consume rate limit)
        if not self.limites.validar_longitud(consulta):
            return self._cerrar(
                mensajes.consulta_larga(self.limites.max_chars), [], "bloqueada", None,
                interfaz, inicio,
            )
        # 2. Rate limit (ventana deslizante por identidad)
        try:
            self.limites.verificar(identidad)
        except LimiteExcedido as exc:
            return self._cerrar(
                mensajes.limite_excedido(exc.reintento_segundos), [], "limitada", None,
                interfaz, inicio,
            )
        # 3. Regex guard (coste cero, antes que cualquier modelo)
        motivo = regex_guard.patron_inyeccion(consulta)
        if motivo:
            registrar_bloqueo(motivo, interfaz)
            return self._cerrar(mensajes.BLOQUEADA, [], "bloqueada", None, interfaz, inicio)
        # 4. Light LM: guard + clasificación + reescritura en UNA llamada
        guardia = light_lm_guard.evaluar_consulta(consulta, self.cliente_light)
        if not guardia.safe:
            registrar_bloqueo("light_lm", interfaz)
            return self._cerrar(
                mensajes.BLOQUEADA, [], "bloqueada", guardia.categoria, interfaz, inicio
            )
        # 5. Fuera de alcance: derivación temprana, sin retrieval ni LLM principal
        if guardia.categoria == "fuera_de_alcance":
            return self._cerrar(
                mensajes.FUERA_ALCANCE, [], "bloqueada", guardia.categoria, interfaz, inicio
            )
        # 6. Retrieval con la consulta reescrita
        fragmentos = retrieval.recuperar(
            guardia.consulta_reescrita,
            self.cliente_embeddings,
            self.almacen,
            top_k=self.top_k,
            min_similitud=self.min_similitud,
        )
        if not fragmentos:
            return self._cerrar(
                mensajes.SIN_RESULTADOS, [], "sin_resultados", guardia.categoria,
                interfaz, inicio,
            )
        # 7. Generación + validación anti-alucinación (1 reintento con feedback)
        respuesta_texto = generacion.generar(consulta, fragmentos, self.cliente_llm)
        if not validacion.validar(respuesta_texto, fragmentos, self.cliente_light):
            respuesta_texto = generacion.generar(
                consulta, fragmentos, self.cliente_llm,
                feedback="afirma solo lo que los fragmentos respaldan",
            )
            if not validacion.validar(respuesta_texto, fragmentos, self.cliente_light):
                return self._cerrar(
                    mensajes.NO_VERIFICADA, [], "sin_resultados", guardia.categoria,
                    interfaz, inicio,
                )
        return self._cerrar(
            respuesta_texto, armar_citas(fragmentos), "ok", guardia.categoria,
            interfaz, inicio,
        )

    def _cerrar(
        self,
        reply: str,
        citas: list[Cita],
        estado: str,
        categoria: str | None,
        interfaz: str,
        inicio: float,
    ) -> Respuesta:
        """Log estructurado por consulta recibida + respuesta final."""
        latencia_ms = int((time.monotonic() - inicio) * 1000)
        registrar_consulta(interfaz, estado, latencia_ms, categoria)
        return Respuesta(reply=reply, citas=citas, estado=estado)


def construir_orquestador() -> Orquestador:
    """Cablea el orquestador con los clientes reales (lo usan ambas interfaces)."""
    return Orquestador(
        limites=LimitesUso(),
        cliente_light=ClienteLightLM(),
        cliente_llm=ClienteLLMPrincipal(),
        cliente_embeddings=ClienteEmbeddings(),
        almacen=AlmacenVectorial(),
    )
