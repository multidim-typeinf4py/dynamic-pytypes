from dataclasses import dataclass
import functools
import itertools
import logging
import operator
import pathlib
from typing import Iterator, NoReturn
import typing

import pandas as pd
import libcst as cst
import libcst.metadata as metadata

from constants import Column
from common import TraceDataCategory
from typegen.strategy.gen import TypeHintGenerator
from typegen.strategy.imports import AddImportTransformer

logger = logging.getLogger(__name__)


@dataclass
class Targets:
    names: list[tuple[str, cst.Name]]
    attrs: list[tuple[str, cst.Attribute]]


class TargetExtractor(cst.CSTVisitor):
    targets: Targets

    def __init__(self):
        self.targets = Targets(list(), list())

    def visit_Subscript(self, node: cst.Subscript) -> bool | None:
        match node.value:
            case cst.Name():
                self.targets.names.append((node.value.value, node.value))
            case cst.Attribute():
                self.targets.attrs.append((node.value.attr.value, node.value))
        return False

    def visit_Name(self, node: cst.Name) -> bool | None:
        self.targets.names.append((node.value, node))
        return False

    def visit_Attribute(self, node: cst.Attribute) -> bool | None:
        self.targets.attrs.append((node.attr.value, node))
        return False


def _find_targets(
    node: cst.Assign | cst.AnnAssign | cst.AugAssign,
) -> Targets:
    extractor = TargetExtractor()

    match node:
        case cst.AnnAssign() | cst.AugAssign():
            node.target.visit(extractor)
        case cst.Assign():
            for target in node.targets:
                target.visit(extractor)
        case _:
            assert False, f"Unsupported node for target searching - {node.__class__.__name__}"

    return extractor.targets


def _create_annotation_from_vartype(vartype: str) -> cst.Annotation:
    return cst.Annotation(annotation=cst.parse_expression(vartype))


class TypeHintTransformer(cst.CSTTransformer):
    """Transforms the CST by adding the traced type hints without modifying the original type hints."""

    METADATA_DEPENDENCIES = (metadata.PositionProvider, metadata.ScopeProvider)

    def __init__(self, module: str, relevant: pd.DataFrame) -> None:
        super().__init__()

        # corner case: NoneType can be hinted with None to avoid needing an import
        self.df = relevant.copy()

        builtin_mask = self.df[Column.VARTYPE_MODULE].isnull()
        nonetype_mask = self.df[Column.VARTYPE] == "NoneType"

        mask = functools.reduce(operator.and_, [builtin_mask, nonetype_mask])
        self.df.loc[mask, Column.VARTYPE] = "None"

        self._module = module

    def _is_in_global_scope(self, node: cst.CSTNode) -> bool:
        match self.get_metadata(metadata.ScopeProvider, node):
            case metadata.GlobalScope():
                return True
            case _:
                return False

    def scopes_of(self, node: cst.CSTNode) -> Iterator[metadata.Scope]:
        if (scope := self.get_metadata(metadata.ScopeProvider, node)) is None:
            return

        yield scope

        match scope:
            case metadata.ClassScope(node=p) | metadata.FunctionScope(node=p):
                yield from self.scopes_of(p)
            case _:
                return

    def _innermost_class(self, node: cst.CSTNode) -> cst.ClassDef | None:
        classes = filter(
            lambda p: isinstance(p, metadata.ClassScope), self.scopes_of(node)
        )

        first: metadata.ClassScope | None = next(classes, None)  # type: ignore
        cdef: cst.ClassDef | None = first.node if first is not None else None  # type: ignore

        return cdef

    def _innermost_function(self, node: cst.CSTNode) -> cst.FunctionDef | None:
        classes = filter(
            lambda p: isinstance(p, metadata.FunctionScope), self.scopes_of(node)
        )

        first: metadata.FunctionScope | None = next(classes, None)  # type: ignore
        fdef: cst.FunctionDef | None = first.node if first is not None else None  # type: ignore

        return fdef

    def _find_visible_globals(
        self, node: cst.Assign | cst.AnnAssign | cst.AugAssign
    ) -> typing.Iterator[str]:
        scopes = self.scopes_of(node)
        global_scope = next(
            filter(lambda scope: isinstance(scope, metadata.GlobalScope), scopes), None
        )

        if global_scope is None:
            return

        yield from global_scope.assignments._assignments.keys()

    def _get_trace_for_targets(
        self, node: cst.Assign | cst.AnnAssign | cst.AugAssign
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, Targets]:
        """
        Fetches trace data for the targets from the given assignment statement.
        Return order is (global variables, local variables, class attributes, targets)
        """

        targets = _find_targets(node)
        target_names = [ident for ident, _ in targets.names]
        if self._is_in_global_scope(node):
            global_var_idents = target_names
            local_var_idents = list()

        else:
            global_var_idents = list(self._find_visible_globals(node))
            local_var_idents = list(set(target_names) - set(global_var_idents))

        attr_idents = [ident for ident, _ in targets.attrs]

        # Crawl over class scopage and analyse available attributes
        containing_classes = list(
            map(
                lambda cs: cs.node,
                filter(
                    lambda scope: isinstance(scope, metadata.ClassScope),
                    self.scopes_of(node),
                ),
            )
        )
        if not len(containing_classes):
            class_mask = self.df[Column.CLASS].isnull()
            class_module_mask = self.df[Column.CLASS_MODULE].isnull()
        else:
            class_names = list(map(lambda c: c.name.value, containing_classes))
            class_mask = self.df[Column.CLASS].isin(class_names)

            # This column can only ever contain project files, as we never
            # trace the internals of files outside of the given project
            # (i.e. no stdlib, no venv etc.), so this check is safe
            class_module_mask = self.df[Column.CLASS_MODULE] == self._module

        pos = self.get_metadata(metadata.PositionProvider, node).start

        local_var_mask = [
            class_module_mask,
            class_mask,
            self.df[Column.LINENO] == pos.line,
            self.df[Column.CATEGORY] == TraceDataCategory.LOCAL_VARIABLE,
            self.df[Column.VARNAME].isin(local_var_idents),
        ]
        attr_mask = [
            class_module_mask,
            class_mask,
            self.df[Column.LINENO] == 0,
            self.df[Column.CATEGORY] == TraceDataCategory.CLASS_MEMBER,
            self.df[Column.VARNAME].isin(attr_idents),
        ]

        global_var_mask = [
            self.df[Column.CLASS_MODULE].isnull(),
            self.df[Column.CLASS].isnull(),
            self.df[Column.LINENO] == 0,
            self.df[Column.CATEGORY] == TraceDataCategory.GLOBAL_VARIABLE,
            self.df[Column.VARNAME].isin(global_var_idents),
        ]

        local_vars = self.df[functools.reduce(operator.and_, local_var_mask)]
        attrs = self.df[functools.reduce(operator.and_, attr_mask)]
        global_vars = self.df[functools.reduce(operator.and_, global_var_mask)]

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
            if self._is_in_global_scope(var):
                logger.debug(f"Searching for '{ident}' in global variables")
                hinted = global_vars[global_vars[Column.VARNAME] == ident]
            else:
                logger.debug(f"Searching for '{ident}' in local variables")
                hinted = local_vars[local_vars[Column.VARNAME] == ident]
        elif isinstance(var, cst.Attribute):
            logger.debug(f"Searching for '{ident}' in class attributes")
            hinted = class_members[class_members[Column.VARNAME] == ident]
        else:
            raise TypeError(f"Unhandled subtype: {type(var)}")
        return hinted

    def _get_trace_for_param(self, node: cst.Param) -> pd.DataFrame:
        # Retrieve outermost function from parent stack
        fdef = self._innermost_function(node)
        assert (
            fdef is not None
        ), f"param {node.name.value} has not been associated with a function"

        scopes = self.scopes_of(node)
        if any(isinstance(s := scope, metadata.ClassScope) for scope in scopes):
            # logger.debug(f"Searching for {node.name} in {s.name}")
            assert hasattr(s, "name")
            clazz_mask = self.df[Column.CLASS] == s.name  # type: ignore
            class_module_mask = self.df[Column.CLASS_MODULE] == self._module
        else:
            # logger.debug(f"Searching for {node.name} outside of class scope")
            clazz_mask = self.df[Column.CLASS].isnull()
            class_module_mask = self.df[Column.CLASS_MODULE].isnull()

        param_masks = [
            clazz_mask,
            class_module_mask,
            self.df[Column.CATEGORY] == TraceDataCategory.CALLABLE_PARAMETER,
            self.df[Column.FUNCNAME] == fdef.name.value,
            self.df[Column.VARNAME] == node.name.value,
        ]
        params = self.df[functools.reduce(operator.and_, param_masks)]
        return params

    def _get_trace_for_rettype(self, node: cst.FunctionDef) -> pd.DataFrame:
        # Retrieve outermost class from parent stack
        # to disambig. methods and functions
        cdef = self._innermost_class(node)
        if cdef is not None:
            clazz_mask = self.df[Column.CLASS] == cdef.name.value
            class_module_mask = self.df[Column.CLASS_MODULE] == self._module
        else:
            clazz_mask = self.df[Column.CLASS].isnull()
            class_module_mask = self.df[Column.CLASS_MODULE].isnull()

        rettype_masks = [
            class_module_mask,
            clazz_mask,
            self.df[Column.LINENO] == 0,  # return type, always stored at line 0
            self.df[Column.CATEGORY] == TraceDataCategory.CALLABLE_RETURN,
            self.df[Column.VARNAME] == node.name.value,
        ]
        rettypes = self.df[functools.reduce(operator.and_, rettype_masks)]
        return rettypes

    def visit_ClassDef(self, cdef: cst.ClassDef) -> bool | None:
        logger.info(f"Entering class '{cdef.name.value}'")

        # Track ClassDefs to disambiguate functions from methods
        return True

    def leave_ClassDef(self, _: cst.ClassDef, updated: cst.ClassDef) -> cst.ClassDef:
        logger.info(f"Leaving class '{updated.name.value}'")
        return updated

    def visit_FunctionDef(self, fdef: cst.FunctionDef) -> bool | None:
        logger.info(f"Entering function '{fdef.name.value}'")
        return True

    def visit_Global(self, node: cst.Global) -> bool | None:
        names = set(map(lambda n: n.name.value, node.names))
        logger.info(f"Registered global(s): '{names}'")

        return True

    def leave_FunctionDef(
        self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
    ) -> cst.FunctionDef:
        logger.info(f"Leaving FunctionDef '{original_node.name.value}'")
        if updated_node.returns is not None:
            logger.warning(
                f"'{original_node.name.value}' already has an annotation, returning."
            )
            return updated_node

        rettypes = self._get_trace_for_rettype(original_node)

        if rettypes.shape[0] > 1:
            self._on_multiple_hints_found(
                original_node.name.value, rettypes, original_node
            )

        returns: cst.Annotation | None

        # no type hint, skip
        if rettypes.empty:
            logger.warning(f"No return type hint found for {original_node.name.value}")
            return updated_node
        else:
            rettype = rettypes[Column.VARTYPE].values[0]
            assert rettype is not None

            logger.info(
                f"Applying return type hint '{rettype}' to '{original_node.name.value}'"
            )
            returns = _create_annotation_from_vartype(rettype)

        return updated_node.with_changes(returns=returns)

    def leave_Param(
        self, original_node: cst.Param, updated_node: cst.Param
    ) -> cst.Param:
        params = self._get_trace_for_param(original_node)
        if params.shape[0] > 1:
            self._on_multiple_hints_found(
                updated_node.name.value,
                params,
                original_node,
            )

        if updated_node.annotation is not None:
            logger.warning(
                f"'{original_node.name.value}' already has an annotation, returning."
            )
            return updated_node

        # no type hint, skip
        if params.empty:
            logger.warning(f"No hint found for parameter '{original_node.name.value}'")
            return updated_node

        argtype = params[Column.VARTYPE].values[0]
        assert argtype is not None

        logger.info(
            f"Applying hint '{argtype}' to parameter '{original_node.name.value}'"
        )
        return updated_node.with_changes(
            annotation=_create_annotation_from_vartype(argtype)
        )

    def leave_AugAssign(
        self, original_node: cst.AugAssign, updated_node: cst.AugAssign
    ) -> cst.FlattenSentinel[cst.BaseSmallStatement]:
        global_vars, local_vars, class_members, targets = self._get_trace_for_targets(
            original_node
        )
        hinted_targets: list[cst.AnnAssign] = []

        for ident, var in itertools.chain(targets.attrs, targets.names):
            hinted = self._load_hint_row_from_frames(
                global_vars, local_vars, class_members, ident, var
            )
            if hinted.empty:
                logger.warning(
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

        global_vars, local_vars, class_members, targets = self._get_trace_for_targets(
            original_node
        )

        hinted_targets: list[cst.AnnAssign] = []

        for ident, var in itertools.chain(targets.attrs, targets.names):
            hinted = self._load_hint_row_from_frames(
                global_vars, local_vars, class_members, ident, var
            )
            if hinted.empty:
                if isinstance(var, cst.Attribute):
                    logger.debug(
                        f"Skipping hint for '{ident}', as annotating "
                        "class members externally is forbidden"
                    )
                else:
                    logger.warning(f"Hint for '{ident}' could not be found")

                logger.warning("Not adding AnnAssign for Assign")
                continue

            if hinted.shape[0] > 1:
                self._on_multiple_hints_found(ident, hinted, original_node)

            hint_ty = hinted[Column.VARTYPE].values[0]
            assert hint_ty is not None

            logger.info(f"Found '{hint_ty}' for '{ident}'")
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
        return cst.FlattenSentinel((*hinted_targets, original_node))

    def leave_AnnAssign(
        self, original_node: cst.AnnAssign, updated_node: cst.AnnAssign
    ) -> cst.Assign | cst.AnnAssign | cst.RemovalSentinel:
        global_vars, local_vars, class_members, targets = self._get_trace_for_targets(
            original_node
        )

        # only one target is possible
        tgt_cnt = len(targets.attrs) + len(targets.names)
        assert (
            tgt_cnt == 1
        ), f"{original_node.target} - Only exactly one target is possible, found {targets.names=}, {targets.attrs=} (len={tgt_cnt})"

        ident, var = next(itertools.chain(targets.attrs, targets.names))
        logger.debug(f"Searching for hints to '{ident}' for an AnnAssign")

        hinted = self._load_hint_row_from_frames(
            global_vars, local_vars, class_members, ident, var
        )
        if hinted.shape[0] > 1:
            self._on_multiple_hints_found(ident, hinted, original_node)

        if hinted.empty and original_node.value is None:
            logger.info(
                "Removing AnnAssign without value because no type hint can be provided"
            )
            return cst.RemoveFromParent()

        elif hinted.empty and original_node.value is not None:
            logger.info(
                "Replacing AnnAssign with value by Assign without type hint because no type hint can be provided"
            )
            return cst.Assign(
                targets=[cst.AssignTarget(original_node.target)],
                value=original_node.value,
            )

        else:
            hint_ty = hinted[Column.VARTYPE].values[0]
            assert hint_ty is not None

            logger.info(f"Using '{hint_ty}' for the AnnAssign with '{ident}'")

            # Replace simple assignment with annotated assignment
            return updated_node.with_changes(
                target=original_node.target,
                annotation=_create_annotation_from_vartype(hint_ty),
                value=original_node.value,
            )

    def _on_multiple_hints_found(
        self, ident: str, hints_found: pd.DataFrame, node: cst.CSTNode
    ) -> NoReturn:
        try:
            stringified = cst.Module([]).code_for_node(node)
        except AttributeError:
            stringified = node.__class__.__name__
        file = self.df[Column.FILENAME].values[0]
        with pd.option_context("display.max_rows", None, "display.max_columns", None):
            raise ValueError(
                f"In {file}: found more than one type hint for {ident}\nNode: {stringified}\n{hints_found}"
            )


class InlineGenerator(TypeHintGenerator):
    """Overwrites the files by adding the traced type hints to the variables. Does not overwrite existing type hints."""

    ident = "inline"

    def _transformers(
        self, module_path: str, applicable: pd.DataFrame
    ) -> list[cst.CSTTransformer]:
        return [
            TypeHintTransformer(module_path, applicable),
            AddImportTransformer(applicable),
        ]

    def _store_hinted_ast(self, source_file: pathlib.Path, hinting: cst.Module) -> None:
        # Inline means overwriting the original
        contents = hinting.code
        with source_file.open("w") as f:
            f.write(contents)
