import typing

import libcst as cst

from . import AnnotationGeneratorStrategy
from .imports import AddImportTransformer

from .remover import HintRemover


class BruteInlineGenerator(AnnotationGeneratorStrategy):
    """Overwrites the files by removing the existing and then adding the traced type hints."""

    ident = "brute"

    def transformers(self) -> typing.Iterator[cst.CSTTransformer]:
        yield from (
            HintRemover(),
            self.provider(context=self.context, traced=self.traced),
            AddImportTransformer(context=self.context, traced=self.traced),
        )


class RetentiveInlineGenerator(AnnotationGeneratorStrategy):
    """Adds annotations only where they are missing"""

    ident = "retentive"

    def transformers(self) -> typing.Iterator[cst.CSTTransformer]:
        yield from (
            self.provider(context=self.context, traced=self.traced),
            AddImportTransformer(context=self.context, traced=self.traced),
        )
