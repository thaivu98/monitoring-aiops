from abc import ABC, abstractmethod

class BaseReceiver(ABC):
    @abstractmethod
    def send(self, subject: str, description: str, metadata: dict) -> bool:
        pass
