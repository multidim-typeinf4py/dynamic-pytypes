import typing

import libcst as cst

from . import AnnotationGenerator
from .imports import AddImportTransformer
from .hinter import TypeHintApplier
from .remover import HintRemover


class BruteInlineGenerator(AnnotationGenerator):
    """Overwrites the files by removing the existing and then adding the traced type hints."""

    ident = "brute"

    def transformers(self) -> typing.Iterator[cst.CSTTransformer]:
        yield from (
            HintRemover(),
            TypeHintApplier(context=self.context, traced=self.traced),
            AddImportTransformer(context=self.context, traced=self.traced),
        )


class RetentiveInlineGenerator(AnnotationGenerator):
    """Adds annotations only where they are missing"""

    ident = "retentive"

    def transformers(self) -> typing.Iterator[cst.CSTTransformer]:
        yield from (
            TypeHintApplier(context=self.context, traced=self.traced),
            AddImportTransformer(context=self.context, traced=self.traced),
        )
