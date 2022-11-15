a: int = 0


class Outer:
    class Inner:
        def __init__(self, f: str) -> None:
            self.attr: str | None = f

    def __init__(self) -> None:
        self.inner: Outer.Inner = Outer.Inner("Hello World")


def outer(b: int, c: int) -> str:
    def inner(d: int, e: int) -> int:
        return d - e

    return f"{inner(b, c)}{inner(c, b)}"


def pain(outer: Outer) -> str:
    old: str = outer.inner.attr
    outer.inner.attr = None

    global a
    a = 10

    return old


def entrypoint() -> None:
    o: Outer = Outer()
    outer_value: str = pain(o)

    of: str = outer(1, 2)
