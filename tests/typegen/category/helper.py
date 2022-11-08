import pathlib
import textwrap

import libcst as cst
import libcst.metadata as metadata

import pandas as pd
import pytest

from tracing.batch import TraceBatch


@pytest.fixture
def typed() -> metadata.MetadataWrapper:
    text = textwrap.dedent(
        """def function(a: int, b: str, c: int) -> int:
    v: str = f'{a}{b}{c}'
    return int(v)

def function_with_multiline_parameters(
    a: str,
    b: int,
    c: str
) -> int:
    v: str = f'{a}{b}{c}'
    return int(v)

class Clazz:
    def method(self, a: int, b: str, c: int) -> tuple:
        return a, b, c

    def multiline_method(
        self, 
        a: str, 
        b: int, 
        c: str
    ) -> tuple:
        return a, b, c

    def function(self, a: A, b: B, c: C) -> int:
        v: str = f'{a}{b}{c}'
        return int(v)
    """
    )

    module = cst.parse_module(text)
    return metadata.MetadataWrapper(module)


@pytest.fixture
def traced() -> pd.DataFrame:
    function = (
        TraceBatch(
            file_name=pathlib.Path("x.py"),
            class_module=None,
            class_name=None,
            function_name="function",
            line_number=1,
        )
        .parameters(
            names2types={
                "a": (None, int.__name__),
                "b": (None, str.__name__),
                "c": (None, int.__name__),
            }
        )
        .returns(names2types={"function": (None, int.__name__)})
        .local_variables(line_number=2, names2types={"v": str.__name__})
        .to_frame()
    )

    function_with_multiline_parameters = (
        TraceBatch(
            file_name=pathlib.Path("x.py"),
            class_module=None,
            class_name=None,
            function_name="function_with_multiline_parameters",
            line_number=5,
        )
        .parameters(
            names2types={
                "a": (None, str.__name__),
                "b": (None, int.__name__),
                "c": (None, str.__name__),
            },
        )
        .returns(
            names2types={"function_with_multiline_parameters": (None, int.__name__)}
        )
        .local_variables(line_number=10, names2types={"v": str.__name__})
        .to_frame()
    )

    method = (
        TraceBatch(
            file_name=pathlib.Path("x.py"),
            class_module="x",
            class_name="Clazz",
            function_name="method",
            line_number=14,
        )
        .parameters(
            {
                "a": (None, int.__name__),
                "b": (None, str.__name__),
                "c": (None, int.__name__),
            }
        )
        .returns(names2types={"method": (None, tuple.__name__)})
        .to_frame()
    )

    multiline_method = (
        TraceBatch(
            file_name=pathlib.Path("x.py"),
            class_module="x",
            class_name="Clazz",
            function_name="multiline_method",
            line_number=17,
        )
        .parameters(
            {
                "a": (None, str.__name__),
                "b": (None, int.__name__),
                "c": (None, str.__name__),
            }
        )
        .returns(names2types={"multiline_method": (None, tuple.__name__)})
        .to_frame()
    )

    function_method = (
        TraceBatch(
            file_name=pathlib.Path("x.py"),
            class_module="x",
            class_name="Clazz",
            function_name="function",
            line_number=25,
        )
        .parameters({"a": (None, "A"), "b": (None, "B"), "c": (None, "C")})
        .returns(names2types={"function": (None, int.__name__)})
        .local_variables(line_number=26, names2types={"v": str.__name__})
        .to_frame()
    )

    return pd.concat(
        [
            function,
            function_with_multiline_parameters,
            method,
            multiline_method,
            function_method,
        ],
        ignore_index=True,
    )
