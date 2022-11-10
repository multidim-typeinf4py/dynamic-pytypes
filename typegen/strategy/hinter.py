import libcst as cst
import libcst.codemod as codemod
from libcst.codemod.visitors._apply_type_annotations import (
    Annotations,
    ApplyTypeAnnotationsVisitor,
)
from libcst.codemod.visitors._apply_type_annotations import (
    FunctionAnnotation,
    FunctionKey,
)

import pandas as pd

from constants import Column
from common.trace_data_category import TraceDataCategory


def _create_annotation(vartype: str) -> cst.Annotation:
    return cst.Annotation(annotation=cst.parse_expression(vartype))


class TypeHintApplier(codemod.ContextAwareTransformer):
    def __init__(self, context: codemod.CodemodContext, traced: pd.DataFrame) -> None:
        super().__init__(context)
        self.traced = traced

    def leave_Module(self, _: cst.Module, updated_node: cst.Module) -> cst.Module:
        visitor = ApplyTypeAnnotationsVisitor(
            context=self.context,
            annotations=Annotations(
                functions=self.functions() | self.methods(),
                attributes=dict(),
                class_definitions=dict(),
                typevars=dict(),
                names=dict(),
            ),
            use_future_annotations=True,
        )

        return visitor.transform_module(updated_node)

    def functions(self) -> dict[FunctionKey, FunctionAnnotation]:
        # Select module level entities
        df = self.traced[
            self.traced[Column.CLASS_MODULE].isnull() & self.traced[Column.CLASS].isnull()
        ]

        d: dict[FunctionKey, FunctionAnnotation] = dict()

        for name, group in df.groupby(
            by=Column.FUNCNAME,
            sort=False,
            dropna=False,
        ):
            param_df = group[group[Column.CATEGORY] == TraceDataCategory.CALLABLE_PARAMETER]
            params = [
                cst.Param(
                    name=cst.Name(value=v),
                    annotation=_create_annotation(t),
                )
                for v, t in param_df[[Column.VARNAME, Column.VARTYPE]].itertuples(index=False)
            ]

            returns_df = group[group[Column.CATEGORY] == TraceDataCategory.CALLABLE_RETURN]
            assert len(returns_df) == 1
            returns = _create_annotation(returns_df[Column.VARTYPE].iloc[0])

            key = FunctionKey.make(name=name, params=cst.Parameters(params))
            value = FunctionAnnotation(parameters=cst.Parameters(params), returns=returns)

            d[key] = value
        return d

    def methods(self):
        # Select class level entities
        df = self.traced[
            self.traced[Column.CLASS_MODULE].notnull() & self.traced[Column.CLASS].notnull()
        ]

        d: dict[FunctionKey, FunctionAnnotation] = dict()

        for (fname, _, cname), group in df.groupby(
            [Column.FUNCNAME, Column.CLASS_MODULE, Column.CLASS],
            sort=False,
            dropna=False,
        ):
            param_df = group[group[Column.CATEGORY] == TraceDataCategory.CALLABLE_PARAMETER]
            params = [
                cst.Param(
                    name=cst.Name(value=v),
                    annotation=_create_annotation(t),
                )
                for v, t in param_df[[Column.VARNAME, Column.VARTYPE]].itertuples(index=False)
            ]

            if "self" not in param_df[Column.VARNAME]:
                params.insert(0, cst.Param(name=cst.Name(value="self")))

            returns_df = group[group[Column.CATEGORY] == TraceDataCategory.CALLABLE_RETURN]
            assert len(returns_df) == 1
            returns = _create_annotation(returns_df[Column.VARTYPE].iloc[0])

            key = FunctionKey.make(name=f"{cname}.{fname}", params=cst.Parameters(params))
            value = FunctionAnnotation(parameters=cst.Parameters(params), returns=returns)

            d[key] = value
        return d
