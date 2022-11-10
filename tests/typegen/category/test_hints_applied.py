import libcst as cst
import libcst.codemod as codemod
import libcst.metadata as metadata

import pandas as pd

from typegen.strategy import remover
from typegen.strategy.inline import RetentiveInlineGenerator

from . import checker


import pytest

from .helper import traced, typed

import difflib


@pytest.mark.parametrize(
    argnames=["chckr", "rmvr"],
    argvalues=[
        (checker.ParameterHintChecker(), remover.ParameterHintRemover()),
        (checker.ReturnHintChecker(), remover.ReturnHintRemover()),
        (checker.AssignHintChecker(), remover.AssignHintRemover()),
    ],
)
def test_category_hinting(
    typed: cst.Module,
    traced: pd.DataFrame,
    chckr: cst.CSTVisitor,
    rmvr: cst.CSTTransformer,
):
    # Test original passes checks
    metadata.MetadataWrapper(typed).visit(chckr)

    # Remove type hints
    removed = metadata.MetadataWrapper(typed).visit(rmvr)
    assert removed.code != typed.code

    # Generate type hints
    generator = RetentiveInlineGenerator(context=codemod.CodemodContext(), traced=traced)
    reinserted = generator.transform_module(tree=removed)

    print(chckr.__class__.__qualname__)
    print(
        "HINTING:",
        "".join(difflib.unified_diff(removed.code.splitlines(1), reinserted.code.splitlines(1))),
        sep="\n",
    )

    # Check inferred
    metadata.MetadataWrapper(reinserted).visit(chckr)
