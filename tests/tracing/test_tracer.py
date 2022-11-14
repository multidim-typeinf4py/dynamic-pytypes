import pathlib

import libcst as cst
import libcst.metadata as metadata
import libcst.codemod as codemod

import pandas as pd

from tracing.tracer import Tracer
from typegen.strategy.inline import BruteInlineGenerator

from tests.helpers.paths import PROJ_PATH, STDLIB_PATH, VENV_PATH
from tests.helpers.checkers import FullyTypedAST


def _compare_dataframes(expected: pd.DataFrame, actual: pd.DataFrame):
    if not (diff := expected.compare(actual)).empty:
        with pd.option_context("display.max_rows", None, "display.max_columns", None):
            print(f"expected:\n{expected}\n\n")
            print(f"actual:\n{actual}\n\n")
            print(f"diff:\n{diff}")
            assert False


def test_trace() -> None:
    traceable = pathlib.Path("tests", "tracing", "traceable.py")
    module = cst.parse_module(source=traceable.open().read())
    metadata.MetadataWrapper(module).visit(FullyTypedAST())

    from tests.tracing.traceable import entrypoint

    tracer = Tracer(proj_path=PROJ_PATH, stdlib_path=STDLIB_PATH, venv_path=VENV_PATH)

    with tracer.active_trace():
        entrypoint()

    print(tracer.trace_data)

    metadata.MetadataWrapper(module).visit(BruteInlineGenerator(
        context=codemod.CodemodContext(filename=str(traceable), full_module_name=)
    ))

    assert False
