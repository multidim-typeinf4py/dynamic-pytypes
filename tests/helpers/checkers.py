import libcst as cst
import libcst.matchers as m
import libcst.metadata as metadata


class TypedParameterAST(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (metadata.ScopeProvider,)

    def visit_Param(self, node: cst.Param) -> bool | None:
        if node.annotation is None and node.name.value != "self":
            scope = self.get_metadata(metadata.ScopeProvider, node)
            raise AssertionError(
                f"Parameter without annotation!:\n{scope.get_qualified_names_for(node.name)}"
            )


class TypedReturnAST(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (metadata.ScopeProvider,)

    def visit_FunctionDef(self, node: cst.FunctionDef) -> bool | None:
        if node.returns is None:
            scope = self.get_metadata(metadata.ScopeProvider, node)
            raise AssertionError(
                f"Function without return hint!:\n{scope.get_qualified_names_for(node)}"
            )


class TypedAssignAST(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (metadata.ScopeProvider, metadata.QualifiedNameProvider)

    def visit_Assign(self, node: cst.Assign) -> bool | None:
        if len(node.targets) != 1:
            return None

        if any(m.matches(target, m.List() | m.Tuple()) for target in node.targets):
            return None

        if m.matches(target := node.targets[0].target, m.Attribute()):
            return None

        scope = self.get_metadata(metadata.ScopeProvider, node)
        if not isinstance(scope, metadata.GlobalScope):
            qnames = scope.get_qualified_names_for(target)
            if all(len(qname.name.split(".")) > 1 for qname in qnames):
                raise AssertionError(
                    f"Assignment without type hint: {scope.get_qualified_names_for(target)}"
                )


class FullyTypedAST(TypedParameterAST, TypedReturnAST, TypedAssignAST):
    ...
