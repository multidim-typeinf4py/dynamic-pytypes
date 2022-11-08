import pathlib

import libcst.metadata as metadata
from libcst import matchers as m
from tracing.batch import TraceBatch

import pandas as pd

from typegen.strats.eval_inline import EvaluationInlineGenerator
from typegen.strats.gen import TypeHintGenerator

from . import helpers
from .helpers import typed


GENERATOR = TypeHintGenerator(
    ident=EvaluationInlineGenerator.ident,
    types=pd.DataFrame(),
)


def test_parameters_are_hinted(typed: metadata.MetadataWrapper):
    # Test original passes checks
    typed.visit(helpers.ParameterHintChecker())

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

    method = (
        TraceBatch(
            file_name=pathlib.Path("x.py"),
            class_module="x",
            class_name="Clazz",
            function_name="method",
            line_number=27,
        )
        .parameters(
            {
                "a": (None, int.__name__),
                "b": (None, str.__name__),
                "c": (None, int.__name__),
            }
        )
        .to_frame()
    )

    multiline_method = (
        TraceBatch(
            file_name=pathlib.Path("x.py"),
            class_module="x",
            class_name="Clazz",
            function_name="multiline_method",
            line_number=27,
        )
        .parameters(
            {
                "a": (None, str.__name__),
                "b": (None, int.__name__),
                "c": (None, str.__name__),
            }
        )
        .to_frame()
    )

    function_method = (
        TraceBatch(
            file_name=pathlib.Path("x.py"),
            class_module="x",
            class_name="Clazz",
            function_name="function",
            line_number=38,
        )
        .parameters({"a": (None, "A"), "b": (None, "B"), "c": (None, "C")})
        .to_frame()
    )

    reinserted = GENERATOR._gen_hinted_ast(
        applicable=pd.concat(
            [
                function,
                function_with_multiline_parameters,
                method,
                multiline_method,
                function_method,
            ]
        ),
        module=removed,
    )

    print(reinserted.code)

    # Check inferred
    metadata.MetadataWrapper(reinserted).visit(helpers.ParameterHintChecker())
