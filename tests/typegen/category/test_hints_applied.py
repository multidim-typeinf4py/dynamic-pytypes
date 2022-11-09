import libcst as cst
import libcst.metadata as metadata

import pandas as pd

from typegen.strategy.eval_inline import InlineGenerator
from typegen.strategy.gen import TypeHintGenerator

from . import checker, remover


import pytest

from .helper import traced, typed

import difflib


GENERATOR = TypeHintGenerator(
    ident=InlineGenerator.ident,
    types=pd.DataFrame(),
)


@pytest.mark.parametrize(
    argnames=["chckr", "rmvr"],
    argvalues=[
        (checker.ParameterHintChecker(), remover.ParameterHintRemover()),
        (checker.ReturnHintChecker(), remover.ReturnHintRemover()),
        (checker.AssignHintChecker(), remover.AssignHintRemover())
    ],
)
def test_category_hinting(
    typed: metadata.MetadataWrapper,
    traced: pd.DataFrame,
    chckr: cst.CSTVisitor,
    rmvr: cst.CSTTransformer,
):
    # Test original passes checks
    typed.visit(chckr)

    # Remove type hints
    removed = typed.visit(rmvr)
    assert removed.code != typed.module.code

    # Generate type hints
    reinserted = GENERATOR._gen_hinted_ast(
        applicable=traced,
        module=removed,
    )

    print(chckr.__class__.__qualname__)
    print(
        "HINTING:",
        "".join(
            difflib.unified_diff(
                removed.code.splitlines(1), reinserted.code.splitlines(1)
            )
        ),
        sep="\n",
    )

    # Check inferred
    metadata.MetadataWrapper(reinserted).visit(chckr)
