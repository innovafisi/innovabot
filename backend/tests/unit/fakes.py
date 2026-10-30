"""Fakes de los clientes externos para tests unitarios (los mocks de LLM son
la norma; las pruebas contra Ollama/RDS reales son de integración)."""

from app.core.modelos import Fragmento


class FakeLightLM:
    """Light LM de prueba: devuelve salidas JSON encoladas y registra llamadas."""

    def __init__(self, *salidas: dict) -> None:
        self._salidas = list(salidas)
        self.llamadas: list[tuple[str, str]] = []

    def completar_json(self, sistema: str, prompt: str, timeout: float = 60.0) -> dict:
        self.llamadas.append((sistema, prompt))
        if not self._salidas:
            raise AssertionError("FakeLightLM sin salidas encoladas")
        return self._salidas.pop(0)


class FakeLLMPrincipal:
    """LLM principal de prueba: devuelve respuestas encoladas y registra llamadas."""

    def __init__(self, *respuestas: str) -> None:
        self._respuestas = list(respuestas)
        self.llamadas: list[tuple[str, str]] = []

    def completar(self, sistema: str, usuario: str) -> str:
        self.llamadas.append((sistema, usuario))
        if not self._respuestas:
            raise AssertionError("FakeLLMPrincipal sin respuestas encoladas")
        return self._respuestas.pop(0)


class FakeEmbeddings:
    """Embeddings de prueba: vectores fijos; registra qué se embebió."""

    def __init__(self) -> None:
        self.llamadas: list[tuple[list[str], bool]] = []

    def embeber(self, textos: list[str], *, es_consulta: bool = False) -> list[list[float]]:
        self.llamadas.append((textos, es_consulta))
        return [[0.1, 0.2, 0.3, 0.4] for _ in textos]


class FakeAlmacen:
    """Almacén vectorial de prueba: resultados fijos; cuenta las búsquedas."""

    def __init__(self, resultados: list[tuple[Fragmento, float]]) -> None:
        self._resultados = resultados
        self.llamadas = 0

    def buscar(
        self, embedding: list[float], top_k: int = 5, boost_faq: float = 0.8
    ) -> list[tuple[Fragmento, float]]:
        self.llamadas += 1
        return self._resultados


def fragmento_prueba(
    id_: str = "hash-1",
    contenido: str = "La matrícula regular va del 10 al 20 de marzo.",
    tipo: str = "noticia",
    url: str = "https://sistemas.unmsm.edu.pe/noticia-1",
    titulo: str = "Calendario de matrícula",
) -> Fragmento:
    return Fragmento(id=id_, contenido=contenido, tipo=tipo, url=url, titulo=titulo)
