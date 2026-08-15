from typing import Type, TypeVar

T = TypeVar("T")

class Registry():

    def __init__(self):
        self._store: dict[str, object] = {}

    def __setitem__(self, key: str | int, value: object) -> None:
        if isinstance(key, int):
            key = str(key)
            if not isinstance(key, str):
                raise TypeError(f"Key must be a str, got {type(key).__name__}")
            self._store[key] = value


    def __setitem__(self, key: str | int, value: object) -> None:
        if isinstance(key, int):
            key = str(key)

        self._store[key] = value


    def get(self, key: str, expected_type: Type[T]) -> T:
        try:
            value = self._store[key]
        except KeyError:
            raise KeyError(f"{key} not found")
        except Exception as e:
            raise ValueError(f"Problem in {key}: {str(e)}")
        if not value:
            raise ValueError(f"{key} is not initialize")
        if not isinstance(value, expected_type):
            raise TypeError(f"{key} is not {expected_type}")
        return value


    def add(self, key: str | int, value: object) -> None:
        if isinstance(key, int):
            key = str(key)
        
        self._store[key] = value

    

Reg = Registry()

    

