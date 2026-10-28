"""Limitador de requisições em memória (janela deslizante).

Simples e sem dependências. Vale para UM processo: se um dia rodarmos vários workers,
cada um terá seu próprio contador (aí trocaríamos por Redis). Para o porte da barbearia basta.
"""
import threading
import time
from collections import defaultdict, deque


class SlidingWindow:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, window: float, now: float) -> deque[float]:
        q = self._hits[key]
        while q and q[0] <= now - window:
            q.popleft()
        if not q:
            self._hits.pop(key, None)  # não acumula chaves antigas na memória
        return q

    def count(self, key: str, window: float) -> int:
        with self._lock:
            return len(self._prune(key, window, time.monotonic()))

    def hit(self, key: str, window: float) -> None:
        with self._lock:
            now = time.monotonic()
            self._prune(key, window, now)
            self._hits[key].append(now)

    def retry_after(self, key: str, window: float) -> int:
        """Segundos até o registro mais antigo sair da janela."""
        with self._lock:
            now = time.monotonic()
            q = self._prune(key, window, now)
            return max(1, int(q[0] + window - now) + 1) if q else 1

    def clear(self, key: str | None = None) -> None:
        with self._lock:
            self._hits.pop(key, None) if key else self._hits.clear()


# Um limitador para o tráfego geral e outro só para falhas de login.
general = SlidingWindow()
login_failures = SlidingWindow()
