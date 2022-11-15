import abc
import functools
import pathlib
import typing

import libcst as cst
import libcst.codemod as codemod
import pandas as pd

from constants import Column

from .hinter import AnnotationProvider


class AnnotationGeneratorStrategy(codemod.Codemod):
    """Base class for different generation styles of type hints,
    including where the result is to be stored"""

    def __init__(
        self,
        context: codemod.CodemodContext,
        provider: typing.Type[AnnotationProvider],
        traced: pd.DataFrame,
    ) -> None:
        super().__init__(context=context)
        self.traced = traced
        self.provider = provider

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


class AnnotationGenStratApplier(codemod.Codemod):
    def __init__(
        self,
        context: codemod.CodemodContext,
        generator_strategy: typing.Type[AnnotationGeneratorStrategy],
        annotation_provider: typing.Type[AnnotationProvider],
        traced: pd.DataFrame,
    ) -> None:
        super().__init__(context=context)
        self.generator_kind = generator_strategy
        self.provider = annotation_provider
        self.traced = traced

    def transform_module_impl(self, tree: cst.Module) -> cst.Module:
        if self.context.filename:
            relative = pathlib.Path(self.context.filename).relative_to(
                self.context.metadata_manager.root_path
            )
            relevant = self.traced[self.traced[Column.FILENAME] == str(relative)]
        else:
            relevant = self.traced

        generator = self.generator_kind(
            context=self.context,
            provider=self.provider,
            traced=relevant,
        )

        return generator.transform_module(tree)


__all__ = [
    AnnotationGeneratorStrategy.__name__,
    AnnotationGenStratApplier.__name__,
]
