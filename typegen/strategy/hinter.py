from dataclasses import dataclass
import functools
import itertools
import logging
import operator
import typing

import libcst as cst
import libcst.codemod as codemod
import libcst.metadata as metadata
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


class AnnotationProvider(codemod.ContextAwareTransformer):
    def __init__(self, context: codemod.CodemodContext, traced: pd.DataFrame) -> None:
        super().__init__(context=context)
        if self.context.filename:
            self.traced = traced[traced[Column.FILENAME] == self.context.filename]
        else:
            self.traced = traced


class LibCSTTypeHintApplier(AnnotationProvider):
    ident = "libcst"

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

                assert (
                    len(returns_df) == 1
                ), f"Found multiple hints for method `{name}`: {returns_df}"
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
            for cname, vname, vtype in group[
                [Column.CLASS, Column.VARNAME, Column.VARTYPE]
            ].itertuples(index=False):
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


@dataclass
class Targets:
    names: list[tuple[str, cst.Name]]
    attrs: list[tuple[str, cst.Attribute]]


class TargetExtractor(cst.CSTVisitor):
    targets: Targets

    def __init__(self):
        self.targets = Targets(list(), list())

    def visit_Attribute(self, node: cst.Attribute) -> bool | None:
        self.targets.attrs.append((node.attr.value, node))
        return False

    def visit_Name(self, node: cst.Name) -> bool | None:
        self.targets.names.append((node.value, node))
        return False


def _find_targets(
    node: cst.Assign | cst.AnnAssign | cst.AugAssign,
) -> Targets:
    extractor = TargetExtractor()
    if isinstance(node, cst.AnnAssign | cst.AugAssign):
        node.target.visit(extractor)
    else:
        for target in node.targets:
            target.visit(extractor)
    return extractor.targets


def _create_annotation_from_vartype(vartype: str) -> cst.Annotation:
    return cst.Annotation(annotation=cst.parse_expression(vartype))


class PyTypesTypeHintApplier(AnnotationProvider):
    """Transforms the CST by adding the traced type hints without modifying the original type hints."""

    METADATA_DEPENDENCIES = (metadata.PositionProvider, metadata.ScopeProvider)

    ident = "pytypes"

    def __init__(self, context: codemod.CodemodContext, traced: pd.DataFrame) -> None:
        super().__init__(context=context, traced=traced)
        self.traced = traced.copy()

        # corner case: NoneType can be hinted with None to avoid needing an import
        builtin_mask = self.traced[Column.VARTYPE_MODULE].isnull()
        nonetype_mask = self.traced[Column.VARTYPE] == "NoneType"

        mask = functools.reduce(operator.and_, [builtin_mask, nonetype_mask])
        self.traced.loc[mask, Column.VARTYPE] = "None"

        self._scope_stack: list[cst.FunctionDef | cst.ClassDef] = []

        self._globals_by_scope: dict[cst.FunctionDef, set[str]] = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    def _is_global_scope(self) -> bool:
        return len(self._scope_stack) == 0

    def _all_scopes_of(self, node: cst.CSTNode) -> typing.Iterator[cst.CSTNode]:
        yield (scope := self.get_metadata(metadata.ScopeProvider, node).parent)

        match scope:
            case metadata.ClassScope(node=p) | metadata.FunctionScope(node=p):
                yield from self._all_scopes_of(p)
            case _:
                return

    def _innermost_class(self) -> cst.ClassDef | None:
        fromtop = reversed(self._scope_stack)
        classes = filter(lambda p: isinstance(p, cst.ClassDef), fromtop)

        first: cst.ClassDef | None = next(classes, None)  # type: ignore
        return first

    def _innermost_function(self) -> cst.FunctionDef | None:
        fromtop = reversed(self._scope_stack)
        fdefs = filter(lambda p: isinstance(p, cst.FunctionDef), fromtop)

        first: cst.FunctionDef | None = next(fdefs, None)  # type: ignore
        return first

    def _find_visible_globals(
        self, node: cst.Assign | cst.AnnAssign | cst.AugAssign
    ) -> typing.Iterator[str]:
        # Check if this is global scope
        if self._is_global_scope():
            # We are in the global scope -> any variable written on this line must be a global!
            # Only consider names, as we are outside of class scope, and we shall not annotate
            # class attributes outside of said class
            self.logger.debug(
                "This is global scope; Using the variables on the given line as globals!"
            )
            yield from map(operator.itemgetter(0), _find_targets(node).names)

        fromtop = reversed(self._scope_stack)
        fdefs = filter(lambda p: isinstance(p, cst.FunctionDef), fromtop)

        # Advance iterator and collect globals
        # mypy fails to narrow the fdef type here
        SENTINEL: set[str] = set()
        yield from (
            glbl
            for fdef in fdefs
            for glbl in self._globals_by_scope.get(fdef, SENTINEL)  # type: ignore
        )

    def _get_trace_for_targets(
        self, node: cst.Assign | cst.AnnAssign | cst.AugAssign
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, Targets]:
        """
        Fetches trace data for the targets from the given assignment statement.
        Return order is (global variables, local variables, class attributes, targets)
        """
        targets = _find_targets(node)
        glbls = set(self._find_visible_globals(node))

        local_var_idents = list()
        global_var_idents = list()

        for ident, _ in targets.names:
            if ident not in glbls:
                self.logger.debug(f"Interpreted '{ident}' as a local variable")
                local_var_idents.append(ident)
            elif self._is_global_scope():
                # Skip the globals if we are not in outer scope
                self.logger.debug(f"Interpreted '{ident}' as a global variable")
                global_var_idents.append(ident)
            else:
                self.logger.debug(
                    f"Skipping '{ident}' during trace collection, as it is 'global', but not in global scopage"
                )

        attr_idents = list(map(operator.itemgetter(0), targets.attrs))

        containing_classes: list[cst.ClassDef] = []

        # Crawl over class stack and analyse available attributes
        # Iterate in reverse to match scope resolution order
        for scope in reversed(self._scope_stack):
            if isinstance(scope, cst.ClassDef):
                containing_classes.append(scope)

        if not len(containing_classes):
            class_mask = self.traced[Column.CLASS].isnull()
            class_module_mask = self.traced[Column.CLASS_MODULE].isnull()
        else:
            class_names = list(map(lambda c: c.name.value, containing_classes))
            class_mask = self.traced[Column.CLASS].isin(class_names)

            # This column can only ever contain project files, as we never
            # trace the internals of files outside of the given project
            # (i.e. no stdlib, no venv etc.), so this check is safe
            class_module_mask = self.traced[Column.CLASS_MODULE] == self.context.full_module_name

        pos = self.get_metadata(metadata.PositionProvider, node).start

        local_var_mask = [
            class_module_mask,
            class_mask,
            self.traced[Column.LINENO] == pos.line,
            self.traced[Column.CATEGORY] == TraceDataCategory.LOCAL_VARIABLE,
            self.traced[Column.VARNAME].isin(local_var_idents),
        ]
        attr_mask = [
            class_module_mask,
            class_mask,
            self.traced[Column.LINENO] == 0,
            self.traced[Column.CATEGORY] == TraceDataCategory.CLASS_MEMBER,
            self.traced[Column.VARNAME].isin(attr_idents),
        ]

        global_var_mask = [
            self.traced[Column.CLASS_MODULE].isnull(),
            self.traced[Column.CLASS].isnull(),
            self.traced[Column.LINENO] == 0,
            self.traced[Column.CATEGORY] == TraceDataCategory.GLOBAL_VARIABLE,
            self.traced[Column.VARNAME].isin(global_var_idents),
        ]

        local_vars = self.traced[functools.reduce(operator.and_, local_var_mask)]
        attrs = self.traced[functools.reduce(operator.and_, attr_mask)]
        global_vars = self.traced[functools.reduce(operator.and_, global_var_mask)]

        return global_vars, local_vars, attrs, targets

    def _load_hint_row_from_frames(
        self,
        global_vars: pd.DataFrame,
        local_vars: pd.DataFrame,
        class_members: pd.DataFrame,
        ident: str,
        var: cst.BaseAssignTargetExpression,
    ) -> pd.DataFrame:
        if isinstance(var, cst.Name):
            if self._is_global_scope():
                self.logger.debug(f"Searching for '{ident}' in global variables")
                hinted = global_vars[global_vars[Column.VARNAME] == ident]
            else:
                line_no = self.get_metadata(metadata.PositionProvider, var).start.line
                self.logger.debug(f"Searching for '{ident}' in local variables on line {line_no}")
                hinted = local_vars[
                    (local_vars[Column.VARNAME] == ident) & (local_vars[Column.LINENO] == line_no)
                ]
        elif isinstance(var, cst.Attribute):
            self.logger.debug(f"Searching for '{ident}' in class attributes")
            hinted = class_members[class_members[Column.VARNAME] == ident]
        else:
            raise TypeError(f"Unhandled subtype: {type(var)}")
        return hinted

    def _get_trace_for_param(self, node: cst.Param) -> pd.DataFrame:
        # Retrieve outermost function from parent stack
        fdef = self._innermost_function()
        assert fdef is not None, f"param {node.name.value} has not been associated with a function"

        scopes = self._all_scopes_of(node)
        if any(isinstance(s := scope, metadata.ClassScope) for scope in scopes):
            self.logger.debug(f"Searching for {node.name} in {s.name}")
            clazz_mask = self.traced[Column.CLASS] == s.name
            class_module_mask = self.traced[Column.CLASS_MODULE] == self.context.full_module_name
        else:
            self.logger.debug(f"Searching for {node.name} outside of class scope")
            clazz_mask = self.traced[Column.CLASS].isnull()
            class_module_mask = self.traced[Column.CLASS_MODULE].isnull()

        param_masks = [
            clazz_mask,
            class_module_mask,
            self.traced[Column.CATEGORY] == TraceDataCategory.CALLABLE_PARAMETER,
            self.traced[Column.FUNCNAME] == fdef.name.value,
            self.traced[Column.VARNAME] == node.name.value,
        ]
        params = self.traced[functools.reduce(operator.and_, param_masks)]
        return params

    def _get_trace_for_rettype(self, node: cst.FunctionDef) -> pd.DataFrame:
        # Retrieve outermost class from parent stack
        # to disambig. methods and functions
        cdef = self._innermost_class()
        if cdef is not None:
            clazz_mask = self.traced[Column.CLASS] == cdef.name.value
            class_module_mask = self.traced[Column.CLASS_MODULE] == self.context.full_module_name
        else:
            clazz_mask = self.traced[Column.CLASS].isnull()
            class_module_mask = self.traced[Column.CLASS_MODULE].isnull()

        rettype_masks = [
            class_module_mask,
            clazz_mask,
            self.traced[Column.LINENO] == 0,  # return type, always stored at line 0
            self.traced[Column.CATEGORY] == TraceDataCategory.CALLABLE_RETURN,
            self.traced[Column.VARNAME] == node.name.value,
        ]
        rettypes = self.traced[functools.reduce(operator.and_, rettype_masks)]
        return rettypes

    def visit_ClassDef(self, cdef: cst.ClassDef) -> bool | None:
        self.logger.info(f"Entering class '{cdef.name.value}'")

        # Track ClassDefs to disambiguate functions from methods
        self._scope_stack.append(cdef)
        return True

    def leave_ClassDef(self, _: cst.ClassDef, updated: cst.ClassDef) -> cst.ClassDef:
        self.logger.info(f"Leaving class '{updated.name.value}'")

        self._scope_stack.pop()
        return updated

    def visit_FunctionDef(self, fdef: cst.FunctionDef) -> bool | None:
        self.logger.info(f"Entering function '{fdef.name.value}'")
        self._scope_stack.append(fdef)
        return True

    def visit_Global(self, node: cst.Global) -> bool | None:
        names = set(map(lambda n: n.name.value, node.names))
        self.logger.info(f"Registered global(s): '{names}'")

        fdef = self._innermost_function()
        assert fdef is not None

        # globals are global for the scope they are currently part of
        self._globals_by_scope[fdef] = names
        return True

    def leave_FunctionDef(
        self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
    ) -> cst.FunctionDef:
        self.logger.info(f"Leaving FunctionDef '{original_node.name.value}'")
        self._scope_stack.pop()

        if original_node in self._globals_by_scope:
            del self._globals_by_scope[original_node]

        if updated_node.returns is not None:
            self.logger.warning(
                f"'{original_node.name.value}' already has an annotation, returning."
            )
            return updated_node

        rettypes = self._get_trace_for_rettype(original_node)

        if rettypes.shape[0] > 1:
            self._on_multiple_hints_found(original_node.name.value, rettypes, original_node)

        returns: cst.Annotation | None

        # no type hint, skip
        if rettypes.empty:
            self.logger.warning(f"No return type hint found for {original_node.name.value}")
            return updated_node
        else:
            rettype = rettypes[Column.VARTYPE].values[0]
            assert rettype is not None

            self.logger.info(
                f"Applying return type hint '{rettype}' to '{original_node.name.value}'"
            )
            returns = _create_annotation_from_vartype(rettype)

        return updated_node.with_changes(returns=returns)

    def leave_Param(self, original_node: cst.Param, updated_node: cst.Param) -> cst.Param:
        params = self._get_trace_for_param(original_node)
        if params.shape[0] > 1:
            self._on_multiple_hints_found(
                updated_node.name.value,
                params,
                original_node,
            )

        if updated_node.annotation is not None:
            self.logger.warning(
                f"'{original_node.name.value}' already has an annotation, returning."
            )
            return updated_node

        # no type hint, skip
        if params.empty:
            self.logger.warning(f"No hint found for parameter '{original_node.name.value}'")
            return updated_node

        argtype = params[Column.VARTYPE].values[0]
        assert argtype is not None

        self.logger.info(f"Applying hint '{argtype}' to parameter '{original_node.name.value}'")
        return updated_node.with_changes(annotation=_create_annotation_from_vartype(argtype))

    def leave_AugAssign(
        self, original_node: cst.AugAssign, updated_node: cst.AugAssign
    ) -> cst.FlattenSentinel[cst.BaseSmallStatement]:
        global_vars, local_vars, class_members, targets = self._get_trace_for_targets(original_node)
        hinted_targets: list[cst.AnnAssign] = []

        for ident, var in itertools.chain(targets.attrs, targets.names):
            hinted = self._load_hint_row_from_frames(
                global_vars, local_vars, class_members, ident, var
            )
            if hinted.empty:
                self.logger.warning(
                    f"No type hint stored for {ident} in AugAssign; Not adding AnnAssign for AugAssign"
                )
                continue
            if hinted.shape[0] > 1:
                self._on_multiple_hints_found(ident, hinted, original_node)

            hint = hinted[Column.VARTYPE].values[0]
            assert hint is not None

            hinted_targets.append(
                cst.AnnAssign(
                    target=var,
                    annotation=_create_annotation_from_vartype(vartype=hint),
                    value=None,
                )
            )
        return cst.FlattenSentinel((*hinted_targets, original_node))

    def leave_Assign(
        self, original_node: cst.Assign, updated_node: cst.Assign
    ) -> cst.Assign | cst.AnnAssign | cst.FlattenSentinel[cst.BaseSmallStatement]:
        # Generate multiple AnnAssigns without values and retain original node if there
        # is more than one target.

        # Otherwise, replace Assign by AnnAssign WITH value
        global_vars, local_vars, class_members, targets = self._get_trace_for_targets(original_node)

        hinted_targets: list[cst.AnnAssign] = []

        for ident, var in itertools.chain(targets.attrs, targets.names):
            hinted = self._load_hint_row_from_frames(
                global_vars, local_vars, class_members, ident, var
            )
            if hinted.empty:
                if isinstance(var, cst.Attribute):
                    self.logger.debug(
                        f"Skipping hint for '{ident}', as annotating "
                        "class members externally is forbidden"
                    )
                if isinstance(var, cst.Subscript):
                    self.logger.debug(
                        f"Skipping hint for '{ident}', as annotating subscripts is forbidden"
                    )

                else:
                    self.logger.warning(f"Hint for '{ident}' could not be found")

                self.logger.warning("Not adding AnnAssign for Assign")
                continue

            if hinted.shape[0] > 1:
                self._on_multiple_hints_found(ident, hinted, original_node)

            hint_ty = hinted[Column.VARTYPE].values[0]
            assert hint_ty is not None

            self.logger.info(f"Found '{hint_ty}' for '{ident}'")
            hinted_targets.append(
                cst.AnnAssign(
                    target=var,
                    annotation=_create_annotation_from_vartype(hint_ty),
                    value=None,
                )
            )

        if len(hinted_targets) == 1:
            annhint = hinted_targets[0]
            # Replace simple assignment with annotated assignment
            return cst.AnnAssign(
                target=annhint.target,
                equal=cst.AssignEqual(),
                annotation=annhint.annotation,
                value=original_node.value,
            )

        # Retain original assignment, prepend AnnAssigns
        return cst.FlattenSentinel((*hinted_targets, updated_node))

    def leave_AnnAssign(
        self, original_node: cst.AnnAssign, updated_node: cst.AnnAssign
    ) -> cst.Assign | cst.AnnAssign | cst.RemovalSentinel:
        global_vars, local_vars, class_members, targets = self._get_trace_for_targets(original_node)

        # only one target is possible
        tgt_cnt = len(targets.attrs) + len(targets.names)
        assert tgt_cnt == 1, f"Only exactly one target is possible, found {tgt_cnt}"

        ident, var = next(itertools.chain(targets.attrs, targets.names))
        self.logger.debug(f"Searching for hints to '{ident}' for an AnnAssign")

        hinted = self._load_hint_row_from_frames(global_vars, local_vars, class_members, ident, var)
        if hinted.shape[0] > 1:
            self._on_multiple_hints_found(ident, hinted, original_node)

        if hinted.empty and original_node.value is None:
            self.logger.info(
                "Removing AnnAssign without value because no type hint can be provided"
            )
            return cst.RemoveFromParent()

        elif hinted.empty and original_node.value is not None:
            self.logger.info(
                "Replacing AnnAssign with value by Assign without type hint because no type hint can be provided"
            )
            return cst.Assign(
                targets=[cst.AssignTarget(original_node.target)],
                value=original_node.value,
            )

        else:
            hint_ty = hinted[Column.VARTYPE].values[0]
            assert hint_ty is not None

            self.logger.info(f"Using '{hint_ty}' for the AnnAssign with '{ident}'")

            # Replace simple assignment with annotated assignment
            return updated_node.with_changes(
                target=original_node.target,
                annotation=_create_annotation_from_vartype(hint_ty),
                value=original_node.value,
            )

    def _on_multiple_hints_found(
        self, ident: str, hints_found: pd.DataFrame, node: cst.CSTNode
    ) -> typing.NoReturn:
        try:
            stringified = cst.Module([]).code_for_node(node)
        except AttributeError:
            stringified = node.__class__.__name__
        file = self.traced[Column.FILENAME].values[0]
        with pd.option_context("display.max_rows", None, "display.max_columns", None):
            raise ValueError(
                f"In {file}: found more than one type hint for {ident}\nNode: {stringified}\n{hints_found}"
            )
