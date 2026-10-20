"""Valor lido do banco uma vez por worker, no primeiro uso, e depois só da memória.

Usado pelas tabelas de cargo e órgão (app/lookup.py) e pela versão dos dados
(app/http_cache.py). Fica em app.extensions: cada worker do Gunicorn tem o seu, nascido
vazio, e só perde o valor quando o processo reinicia (reciclagem do worker ou do container).
"""

import threading
from collections.abc import Callable


class Lazy[T]:
    """Carrega o valor na primeira chamada de get(), uma vez só, mesmo com várias threads."""

    def __init__(self, load: Callable[[], T]) -> None:
        self._load = load
        # O worker gthread atende várias requisições ao mesmo tempo: só uma thread carrega,
        # as outras esperam por ela em vez de repetir a consulta.
        self._lock = threading.Lock()
        self._value: T | None = None

    def get(self) -> T:
        """O valor, carregando-o se ainda não foi. Se a carga falhar, a próxima chamada tenta
        de novo. Quem chama não pode estar segurando uma conexão do pool: a carga pega a sua.
        """
        value = self._value
        if value is None:
            with self._lock:
                # Outra thread pode ter carregado enquanto esta esperava o lock.
                if self._value is None:
                    self._value = self._load()
                value = self._value
        return value

    def peek(self) -> T | None:
        """O valor já carregado, ou None, sem nunca ir ao banco."""
        return self._value
