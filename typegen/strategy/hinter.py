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
        if context.filename:
            self.traced = traced[traced[Column.FILENAME] == self.context.filename]
        else:
            self.traced = traced

    def leave_Module(self, _: cst.Module, updated_node: cst.Module) -> cst.Module:
        visitor = ApplyTypeAnnotationsVisitor(
            context=self.context,
            annotations=Annotations(
                functions=self.functions() | self.methods(),
                attributes=self.globals() | self.locals(),
                class_definitions=self.members(),
                typevars=dict(),
                names=set(),
            ),
            use_future_annotations=True,
            handle_function_bodies=True,
            create_class_attributes=True,
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
            assert len(returns_df) == 1, f"Found multiple hints for function `{name}`: {returns_df}"
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
            if not returns_df.empty:
                name = f"{cname}.{fname}"

                assert len(returns_df) == 1, f"Found multiple hints for method `{name}`: {returns_df}"
                returns = _create_annotation(returns_df[Column.VARTYPE].iloc[0])

                key = FunctionKey.make(name=name, params=cst.Parameters(params))
                value = FunctionAnnotation(parameters=cst.Parameters(params), returns=returns)

                d[key] = value
        return d

    def globals(self) -> dict[str, cst.Annotation]:
        df = self.traced[(self.traced[Column.CATEGORY] == TraceDataCategory.GLOBAL_VARIABLE)]
        d: dict[str, cst.Annotation] = dict()

        for vname, group in df.groupby(by=Column.VARNAME, sort=False, dropna=False):
            assert len(group) == 1, f"Found multiple hints for {vname} - {group}"
            d[vname] = _create_annotation(group[Column.VARTYPE].iloc[0])

        return d

    def locals(self) -> dict[str, cst.Annotation]:
        df = self.traced[(self.traced[Column.CATEGORY] == TraceDataCategory.LOCAL_VARIABLE)]
        d: dict[str, cst.Annotation] = dict()

        for fname, group in df.groupby(by=Column.FUNCNAME, sort=False, dropna=False):
            for cname, vname, vtype in group[[Column.CLASS, Column.VARNAME, Column.VARTYPE]].itertuples(index=False):
                name = f"{fname}.{vname}" if pd.isnull(cname) else f"{cname}.{fname}.{vname}"
                d[name] = _create_annotation(vtype)

        return d

    def members(self) -> dict[str, cst.ClassDef]:
        df = self.traced[self.traced[Column.CATEGORY] == TraceDataCategory.CLASS_MEMBER]
        d: dict[str, cst.ClassDef] = dict()

        for cname, group in df.groupby(by=Column.CLASS, sort=False, dropna=True):
            hints: list[cst.BaseStatement] = list()
            for vname, vtype in group[[Column.VARNAME, Column.VARTYPE]].itertuples(index=False):
                hints.append(
                    cst.SimpleStatementLine(
                        body=[
                            cst.AnnAssign(
                                target=cst.Name(value=vname), annotation=_create_annotation(vtype)
                            )
                        ]
                    )
                )

            d[cname] = cst.ClassDef(name=cst.Name(cname), body=cst.IndentedBlock(body=hints))

        return d
