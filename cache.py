import json
from abc import abstractmethod, ABC
from json import JSONDecodeError
from pathlib import Path
from typing import List


class Cache(ABC):
    """
    Abstract contract for caches to implement by requiring this abstract class instead of any of its concrete implementations one could
    swap cache types without breaking any code `loosely coupled`.
    """
    @abstractmethod
    def contains(self, item) -> bool:
        pass

    @abstractmethod
    def size(self) -> int:
        pass

    @abstractmethod
    def remove(self, item):
        pass

    @abstractmethod
    def add(self, key, value):
        pass

    @abstractmethod
    def get(self, item):
        pass

    @abstractmethod
    def reconstruct(self):
        pass

    @abstractmethod
    def commit(self, ):
        pass


class JsonCache(Cache):
    """Cache implementation that works with a """
    def __str__(self):
        for k, v in self.cache:
            print(f'file={k}, image={v}')

    def __init__(self, ):
        self.cache: List[dict] = []

    def from_file(self, file: Path, ):
        try:
            self.cache = json.loads(file.read_text())
            return self.cache
        except JSONDecodeError:
            self.cache = []

    def contains(self, filename) -> bool:
        for item in self.cache:
            if item['filename'] == filename:
                return True
        return False

    def size(self) -> int:
        return len(self.cache)

    def remove(self, item):
        del self.cache[item]

    def add(self, key, value):
        self.cache[key] = value

    def get(self, filename):
        for item in self.cache:
            if item['filename'] == filename:
                return item
        return None

    def reconstruct(self):
        raise NotImplementedError

    def commit(self):
        raise NotImplementedError
