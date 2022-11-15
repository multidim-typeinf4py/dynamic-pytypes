class A:
    def __str__(self) -> str:
        return self.__class__.__qualname__


class B:
    def __str__(self) -> str:
        return self.__class__.__qualname__


class C:
    def __str__(self) -> str:
        return self.__class__.__qualname__


def function(a: int, b: str, c: int) -> int:
    v: str = f"{a}{b}{c}"
    return int(v)


def function_with_multiline_parameters(a: str, b: int, c: str) -> int:
    v: str = f"{a}{b}{c}"
    return int(v)


class Clazz:
    def __init__(self, a: int) -> None:
        self.a: int = a

    def method(self, a: int, b: str, c: int) -> tuple:
        return a, b, c

    def multiline_method(self, a: str, b: int, c: str) -> tuple:
        return a, b, c

    def function(self, a: A, b: B, c: C) -> str:
        v: str = f"{a}{b}{c}"
        return v

def outer_function() -> int:
    def nested_function(a: int) -> str:
        return str(a)

    return int(nested_function(10))


a: int = 5
e: int
z: str
p: int
zee: bytes
clazz: Clazz
e, z, p, zee, clazz = a, "Hello World!", 123, b"b.c", Clazz(10)
