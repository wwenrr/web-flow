from typing import TypeVar, Type

T = TypeVar('T')


class Singleton:
    """
    Base Singleton class for reusable singleton pattern.
    Inherit from this class to create singleton instances.
    """
    
    _instances: dict[Type, object] = {}
    
    def __new__(cls: Type[T]) -> T:
        if cls not in cls._instances:
            cls._instances[cls] = super().__new__(cls)
        return cls._instances[cls]

