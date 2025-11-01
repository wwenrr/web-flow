from abc import ABC, abstractmethod
from typing import Any


class BaseWorkFlow(ABC):
    """
    Base class for all workflows.
    """
    
    @abstractmethod
    def execute(self, input_data: Any = None):
        raise NotImplementedError("Subclasses must implement this method")