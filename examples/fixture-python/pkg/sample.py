"""Fixture module exercising the range of Python symbol shapes."""

from functools import lru_cache


def capitalise_string(value: str) -> str:
    """Capitalises the string."""
    return value[:1].upper() + value[1:]


def undocumented_add(a: int, b: int) -> int:
    return a + b


# autodoc: ignore
def ignored_by_marker() -> None:
    return None


@lru_cache(maxsize=None)
def cached_lookup(key: str) -> str:
    """Looks up a value, cached because the backing store is a slow network call."""
    return key.upper()


async def fetch_data(url: str) -> bytes:
    """Fetches raw bytes from `url`."""
    return b""


def outer(values: list[int]) -> list[int]:
    """Doubles every even value, dropping odd ones."""

    def inner(v: int) -> int:
        return v * 2

    return [inner(v) for v in values if v % 2 == 0]


def number_stream(n: int):
    """Yields integers from 0 up to (not including) n."""
    for i in range(n):
        yield i


class Widget:
    """A widget with a name and a size."""

    def __init__(self, name: str, size: int) -> None:
        self.name = name
        self._size = size

    @property
    def size(self) -> int:
        """The widget's size."""
        return self._size

    def resize(self, delta: int) -> None:
        self._size += delta

    @staticmethod
    def default() -> "Widget":
        """Builds the default widget."""
        return Widget("default", 1)
