from abc import ABC, abstractmethod
from typing import Optional, Tuple


class BaseDomainEngine(ABC):
    """
    Interfaccia formale per tutti i motori di precondizionamento strutturale di KolmoX.
    Ogni motore opera come un filtro deterministico reversibile a monte dell'entropy coding.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Nome identificativo del motore di dominio."""
        pass

    @abstractmethod
    def transform(self, data: bytes) -> Tuple[bytes, bytes]:
        """
        Applica la trasformazione strutturale.
        Ritorna una tupla (primary_payload, aux_payload).
        """
        pass

    @abstractmethod
    def inverse_transform(self, primary: bytes, aux: bytes = b"") -> bytes:
        """Inverte la trasformazione ricostruendo esattamente i dati grezzi originali."""
        pass

    @abstractmethod
    def applicable(self, data: bytes, filename: Optional[str] = None) -> bool:
        """Euristica leggera o check magico per verificare se i dati appartengono al dominio."""
        pass
