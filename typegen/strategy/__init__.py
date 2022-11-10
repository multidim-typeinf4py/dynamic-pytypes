import abc
import functools
import typing

import libcst as cst
import libcst.codemod as codemod
import pandas as pd

from constants import Column


class AnnotationGenerator(codemod.Codemod):
    """Base class for different generation styles of type hints,
    including where the result is to be stored"""

    def __init__(self, context: codemod.CodemodContext, traced: pd.DataFrame) -> None:
        super().__init__(context=context)
        self.traced = traced

    def transform_module_impl(self, tree: cst.Module) -> cst.Module:
        return functools.reduce(
            lambda m, t: cst.MetadataWrapper(m).visit(t),
            self.transformers(),
            tree,
        )

    @property
    @abc.abstractmethod
    def ident(self) -> str:
        pass

    @abc.abstractmethod
    def transformers(self) -> typing.Iterator[cst.CSTTransformer]:
        pass


class AnnotationGeneratorApplier(codemod.Codemod):
    def __init__(
        self,
        context: codemod.CodemodContext,
        generator_kind: typing.Type[AnnotationGenerator],
        traced: pd.DataFrame,
    ) -> None:
        super().__init__(context=context)
        self.generator_kind = generator_kind
        self.traced = traced

    def transform_module_impl(self, tree: cst.Module) -> cst.Module:
        relevant = self.traced[
            self.traced[Column.FILENAME] == str(self.context.filename)
        ]
        generator = self.generator_kind(
            context=self.context,
            traced=relevant,
        )

        return generator.transform_module(tree)


__all__ = [
    AnnotationGenerator.__name__,
    AnnotationGeneratorApplier.__name__,
]
