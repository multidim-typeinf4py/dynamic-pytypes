import pathlib
import textwrap

import libcst as cst
import libcst.metadata as metadata
from libcst import matchers as m
from tracing.batch import TraceBatch, TraceUpdateOverride

import pandas as pd

from typegen.strats.eval_inline import EvaluationInlineGenerator
from typegen.strats.gen import TypeHintGenerator

from . import helpers

import pytest


GENERATOR = TypeHintGenerator(
    ident=EvaluationInlineGenerator.ident,
    types=pd.DataFrame(),
)


@pytest.fixture
def typed() -> metadata.MetadataWrapper:
    text = textwrap.dedent(
        """
def function(a: int, b: str, c: int) -> int:
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
    def method(self, a: int, b: str, c: int) -> tuple[int, str, int]:
        return a, b, c

    def multiline_method(
        self, 
        a: str, 
        b: int, 
        c: str
    ) -> tuple[str, int, str]:
        return a, b, c

    def function(self, a: A, b: B, c: C) -> int:
        v: str = f'{a}{b}{c}'
        return int(v)
    """
    )

    module = cst.parse_module(text)
    return metadata.MetadataWrapper(module)


class ParameterHintChecker(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (metadata.ScopeProvider,)

    FUNCTION_MATCHERS = (
        m.FunctionDef(
            name=m.Name(value="function"),
            params=m.Parameters(
                params=[
                    m.Param(
                        name=m.Name(value="a"),
                        annotation=m.Annotation(annotation=m.Name(value="int")),
                    ),
                    m.Param(
                        name=m.Name(value="b"),
                        annotation=m.Annotation(annotation=m.Name(value="str")),
                    ),
                    m.Param(
                        name=m.Name(value="c"),
                        annotation=m.Annotation(annotation=m.Name(value="int")),
                    ),
                ]
            ),
        ),
        m.FunctionDef(
            name=m.Name(value="function_with_multiline_parameters"),
            params=m.Parameters(
                params=[
                    m.Param(
                        name=m.Name(value="a"),
                        annotation=m.Annotation(annotation=m.Name(value="str")),
                    ),
                    m.Param(
                        name=m.Name(value="b"),
                        annotation=m.Annotation(annotation=m.Name(value="int")),
                    ),
                    m.Param(
                        name=m.Name(value="c"),
                        annotation=m.Annotation(annotation=m.Name(value="str")),
                    ),
                ]
            ),
        ),
    )

    METHOD_MATCHERS = (
        m.FunctionDef(
            name=m.Name(value="method"),
            params=m.Parameters(
                params=[
                    m.Param(name=m.Name(value="self")),
                    m.Param(
                        name=m.Name(value="a"),
                        annotation=m.Annotation(annotation=m.Name(value="int")),
                    ),
                    m.Param(
                        name=m.Name(value="b"),
                        annotation=m.Annotation(annotation=m.Name(value="str")),
                    ),
                    m.Param(
                        name=m.Name(value="c"),
                        annotation=m.Annotation(annotation=m.Name(value="int")),
                    ),
                ]
            ),
        ),
        m.FunctionDef(
            name=m.Name(value="multiline_method"),
            params=m.Parameters(
                params=[
                    m.Param(name=m.Name(value="self")),
                    m.Param(
                        name=m.Name(value="a"),
                        annotation=m.Annotation(annotation=m.Name(value="str")),
                    ),
                    m.Param(
                        name=m.Name(value="b"),
                        annotation=m.Annotation(annotation=m.Name(value="int")),
                    ),
                    m.Param(
                        name=m.Name(value="c"),
                        annotation=m.Annotation(annotation=m.Name(value="str")),
                    ),
                ]
            ),
        ),
        m.FunctionDef(
            name=m.Name(value="function"),
            params=m.Parameters(
                params=[
                    m.Param(name=m.Name(value="self")),
                    m.Param(
                        name=m.Name(value="a"),
                        annotation=m.Annotation(annotation=m.Name(value="A")),
                    ),
                    m.Param(
                        name=m.Name(value="b"),
                        annotation=m.Annotation(annotation=m.Name(value="B")),
                    ),
                    m.Param(
                        name=m.Name(value="c"),
                        annotation=m.Annotation(annotation=m.Name(value="C")),
                    ),
                ]
            ),
        ),
    )

    def visit_FunctionDef(self, node: cst.FunctionDef) -> bool:
        scope = self.get_metadata(metadata.ScopeProvider, node)
        print(type(scope))

        # Function
        if isinstance(scope, metadata.GlobalScope):
            assert any(
                m.matches(node, fm) for fm in ParameterHintChecker.FUNCTION_MATCHERS
            ), f"{ParameterHintChecker.__name__} - Failed to match function `{node.name.value}`"

        # Method
        elif isinstance(scope, metadata.ClassScope):
            assert any(
                m.matches(node, fm) for fm in ParameterHintChecker.METHOD_MATCHERS
            ), f"{ParameterHintChecker.__name__} - Failed to match method `{node.name.value}`"

        return False


class ReturnHintChecker(cst.CSTVisitor):
    FUNCTION_MATCHERS = (
        m.FunctionDef(
            name="function", returns=m.Annotation(annotation=m.Name(value="int"))
        ),
        m.FunctionDef(
            name="function_with_multiline_parameters",
            returns=m.Annotation(annotation=m.Name(value="int")),
        ),
    )

    METHOD_MATCHERS = (
        m.FunctionDef(
            name="method",
            returns=m.Annotation(
                annotation=m.Subscript(
                    value=m.Name("tuple"),
                    slice=[
                        m.SubscriptElement(slice=m.Index(value=m.Name(ty)))
                        for ty in ("int", "str", "int")
                    ],
                )
            ),
        ),
        m.FunctionDef(
            name="multiline_method",
            returns=m.Annotation(
                annotation=m.Subscript(
                    value=m.Name("tuple"),
                    slice=[
                        m.SubscriptElement(slice=m.Index(value=m.Name(t)))
                        for t in ("str", "int", "str")
                    ],
                )
            ),
        ),
        m.FunctionDef(
            name="function", returns=m.Annotation(annotation=m.Name(value="int"))
        ),
    )


def test_parameters_are_hinted(typed: metadata.MetadataWrapper):
    # Test original passes checks
    typed.visit(ParameterHintChecker())

    # Remove type hints
    removed = typed.visit(helpers.ParameterHintRemover())

    # Reinsert type hints
    function = (
        TraceBatch(
            file_name=pathlib.Path("x.py"),
            class_module=None,
            class_name=None,
            function_name="function",
            line_number=2,
        )
        .parameters(
            names2types={
                "a": (None, int.__name__),
                "b": (None, str.__name__),
                "c": (None, int.__name__),
            }
        )
        .to_frame()
    )

    function_with_multiline_parameters = (
        TraceBatch(
            file_name=pathlib.Path("x.py"),
            class_module=None,
            class_name=None,
            function_name="function_with_multiline_parameters",
            line_number=7,
        )
        .parameters(
            names2types={
                "a": (None, str.__name__),
                "b": (None, int.__name__),
                "c": (None, str.__name__),
            },
        )
        .to_frame()
    )

    reinserted = GENERATOR._gen_hinted_ast(
        applicable=pd.concat([function, function_with_multiline_parameters]),
        module=removed,
    )

    print(reinserted.code)

    # Check inferred
    metadata.MetadataWrapper(reinserted).visit(ParameterHintChecker())
