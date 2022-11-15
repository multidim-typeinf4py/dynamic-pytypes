
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
from typegen.provider import AnnotationProvider


class LibCSTTypeHintApplier(AnnotationProvider):
    ident = "libcst"

    def __init__(self, context: codemod.CodemodContext, traced: pd.DataFrame) -> None:
        super().__init__(context, traced)

    def leave_Module(self, _: cst.Module, updated_node: cst.Module) -> cst.Module:
        self.logger.info(f"Hinting {self.context.filename}")

        functions = self.functions()
        self.logger.debug(f"Functions: {list(key.name for key in functions.keys())}")

        methods = self.methods()
        self.logger.debug(f"Methods: {list(key.name for key in methods.keys())}")

        glbls = self.globals()
        self.logger.debug(f"Globals: {list(key for key in glbls.keys())}")

        lcls = self.locals()
        self.logger.debug(f"Locals: {list(key for key in lcls.keys())}")

        members = self.members()
        self.logger.debug(f"Members for: {list(key for key in members.keys())}")

        assert all(fn := fname not in methods for fname in functions), f"Key clash between functions and methods: {fn}"
        assert all(v := vname not in glbls for vname in lcls), f"Key clash between locals and globals: {v}"

        visitor = ApplyTypeAnnotationsVisitor(
            context=self.context,
            annotations=Annotations(
                functions=functions | methods,
                attributes=glbls | lcls,
                class_definitions=members,
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
                    annotation=self._create_annotation(t),
                )
                for v, t in param_df[[Column.VARNAME, Column.VARTYPE]].itertuples(index=False)
            ]

            returns_df = group[group[Column.CATEGORY] == TraceDataCategory.CALLABLE_RETURN]
            if not len(returns_df):
                continue
            assert len(returns_df) == 1, f"Found multiple hints for function `{name}`: {returns_df}"
            returns = self._create_annotation(returns_df[Column.VARTYPE].iloc[0])

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

        for fname, group in df.groupby(
            by=Column.FUNCNAME,
            sort=False,
            dropna=False,
        ):
            param_df = group[group[Column.CATEGORY] == TraceDataCategory.CALLABLE_PARAMETER]
            params = [
                cst.Param(
                    name=cst.Name(value=v),
                    annotation=self._create_annotation(t),
                )
                for v, t in param_df[[Column.VARNAME, Column.VARTYPE]].itertuples(index=False)
            ]

            returns_df = group[group[Column.CATEGORY] == TraceDataCategory.CALLABLE_RETURN]
            if returns_df.empty:
                continue

            assert (
                len(returns_df) == 1
            ), f"Found multiple hints for method `{fname}`: {returns_df}"
            returns = self._create_annotation(returns_df[Column.VARTYPE].iloc[0])

            key = FunctionKey.make(name=fname, params=cst.Parameters(params))
            value = FunctionAnnotation(parameters=cst.Parameters(params), returns=returns)
            d[key] = value
            
        return d

    def globals(self) -> dict[str, cst.Annotation]:
        df = self.traced[(self.traced[Column.CATEGORY] == TraceDataCategory.GLOBAL_VARIABLE)]
        d: dict[str, cst.Annotation] = dict()

        for vname, group in df.groupby(by=Column.VARNAME, sort=False, dropna=False):
            assert len(group) == 1, f"Found multiple hints for {vname} - {group}"
            d[vname] = self._create_annotation(group[Column.VARTYPE].iloc[0])

        return d

    def locals(self) -> dict[str, cst.Annotation]:
        df = self.traced[(self.traced[Column.CATEGORY] == TraceDataCategory.LOCAL_VARIABLE)]
        d: dict[str, cst.Annotation] = dict()

        for fname, group in df.groupby(by=Column.FUNCNAME, sort=False, dropna=False):
            for vname, vtype in group[[Column.VARNAME, Column.VARTYPE]].itertuples(index=False):
                name = f"{fname}.{vname}"
                d[name] = self._create_annotation(vtype)

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
                                target=cst.Name(value=vname), annotation=self._create_annotation(vtype)
                            )
                        ]
                    )
                )

            d[cname] = cst.ClassDef(name=cst.Name(cname), body=cst.IndentedBlock(body=hints))

        return d
