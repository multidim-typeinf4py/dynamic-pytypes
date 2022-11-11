import functools
import operator
import os
import libcst as cst

from libcst import codemod

import pandas as pd

from constants import Column


class AddImportTransformer(cst.CSTTransformer):
    """Transforms the CST by adding Import nodes to import the modules of
    the type hints according to the trace data."""

    def __init__(self, context: codemod.CodemodContext, traced: pd.DataFrame) -> None:
        self.context = context
        self.traced = traced.copy()

    def leave_Module(self, _: cst.Module, tree: cst.Module) -> cst.Module:
        from libcst.codemod.visitors._add_imports import AddHintableImportsVisitor

        def file2module(file: str) -> str:
            return os.path.splitext(file.replace(os.path.sep, "."))[0]

        # Stupid implementation: make from x import y everywhere
        self.traced["modules"] = self.traced[Column.FILENAME].map(lambda f: file2module(f))

        # ignore builtins
        non_builtin = self.traced[Column.VARTYPE_MODULE].notnull()
        # ignore classes in the same module
        not_in_same_mod = self.traced["modules"] != self.traced[Column.VARTYPE_MODULE]
        retain_mask = [non_builtin, not_in_same_mod]

        important = self.traced[functools.reduce(operator.and_, retain_mask)]
        if important.empty:
            return tree

        importables = important.groupby(
            by=[Column.VARTYPE_MODULE, Column.VARTYPE], sort=False, dropna=False
        )

        for _, group in importables:
            modules = group[Column.VARTYPE_MODULE].values[0]
            types = group[Column.VARTYPE].values[0]

            modules = modules.split(",")
            types = types.split(" | ")

            for module, ty in zip(modules, types):
                AddHintableImportsVisitor.add_needed_import(
                    context=self.context, module=module, obj=ty, for_type_hint=True
                )

        add_imports_visitor = AddHintableImportsVisitor(context=self.context)
        return add_imports_visitor.transform_module(tree)
