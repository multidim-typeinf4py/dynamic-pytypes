import difflib
import pathlib
import pytest

import libcst as cst
import libcst.codemod as codemod

from tracing.batch import TraceBatch
from typegen.strategy.inline import BruteInlineGenerator
from typegen.strategy.hinter import LibCSTTypeHintApplier


@pytest.fixture
def generator(scope="function") -> BruteInlineGenerator:
    batch = TraceBatch(
        file_name=pathlib.Path("tests", "typegen", "strats", "test_import.py"),
        class_module=None,
        class_name=None,
        function_name="f",
        line_number=1,
    )

    batch = batch.returns(names2types={"f": ("mycool", "Ty")})

    return BruteInlineGenerator(
        context=codemod.CodemodContext(), provider=LibCSTTypeHintApplier, traced=batch.to_frame()
    )


@pytest.fixture
def no_future_import() -> tuple[cst.Module, cst.Module]:
    contents = r"""def f(): return 5"""
    expected = r"""from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from mycool import Ty

def f() -> Ty: return 5"""

    return cst.parse_module(contents), cst.parse_module(expected)


def diff(expected: cst.Module, actual: cst.Module) -> str:
    return "".join(difflib.unified_diff(expected.code.splitlines(1), actual.code.splitlines(1)))


def test_missing_annotation_import_added(
    generator: BruteInlineGenerator, no_future_import: tuple[cst.Module, cst.Module]
):
    contents, expected = no_future_import
    output = generator.transform_module(contents)

    if expected.code != output.code:
        assert False, diff(expected, output)
