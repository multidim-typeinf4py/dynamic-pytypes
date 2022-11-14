import typing
import libcst as cst
import libcst.codemod as codemod
import libcst.metadata as metadata

import pandas as pd

from typegen.strategy import hinter
from typegen.strategy import remover
from typegen.strategy import inline

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
@pytest.mark.parametrize(
    argnames=["provider"],
    argvalues=[(hinter.LibCSTTypeHintApplier,), (hinter.PyTypesTypeHintApplier,)],
)
def test_category_hinting(
    typed: cst.Module,
    traced: pd.DataFrame,
    provider: typing.Type[hinter.AnnotationProvider],
    chckr: cst.CSTVisitor,
    rmvr: cst.CSTTransformer,
):
    # Test original passes checks
    try:
        metadata.MetadataWrapper(typed).visit(chckr)
    except Exception as e:
        raise Exception(
            f"Original AST failed to pass checks! - Config: {provider.__qualname__}, {chckr.__class__.__name__}, {rmvr.__class__.__name__}"
        ) from e

    # Remove type hints
    removed = metadata.MetadataWrapper(typed).visit(rmvr)
    assert removed.code != typed.code
    print(
        "REMOVAL:",
        "".join(difflib.unified_diff(typed.code.splitlines(1), removed.code.splitlines(1))),
        sep="\n",
    ),

    # Generate type hints
    context = codemod.CodemodContext(filename="x.py", full_module_name="x", full_package_name="x")
    generator = inline.RetentiveInlineGenerator(context=context, provider=provider, traced=traced)
    reinserted = generator.transform_module(tree=removed)

    print(chckr.__class__.__qualname__)
    print(
        "HINTING:",
        "".join(difflib.unified_diff(removed.code.splitlines(1), reinserted.code.splitlines(1))),
        sep="\n",
    )

    # Check inferred
    try:
        metadata.MetadataWrapper(reinserted).visit(chckr)
    except Exception as e:
        raise Exception(
            f"Reinserted AST failed to pass checks! - Config: {provider.__qualname__}, {chckr.__class__.__name__}, {rmvr.__class__.__name__}"
        ) from e
