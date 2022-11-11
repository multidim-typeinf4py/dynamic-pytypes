import libcst as cst
import libcst.metadata as metadata
import libcst.matchers as m


class ParameterHintChecker(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (metadata.ScopeProvider,)

    FUNCTION_MATCHERS = (
        m.FunctionDef(
            name=m.Name(value="function"),
            params=m.Parameters(
                params=[
                    m.Param(
                        name=m.Name(value="a"),
                        annotation=m.Annotation(annotation=m.Name(value="int")),
                    ),
                    m.Param(
                        name=m.Name(value="b"),
                        annotation=m.Annotation(annotation=m.Name(value="str")),
                    ),
                    m.Param(
                        name=m.Name(value="c"),
                        annotation=m.Annotation(annotation=m.Name(value="int")),
                    ),
                ]
            ),
        ),
        m.FunctionDef(
            name=m.Name(value="function_with_multiline_parameters"),
            params=m.Parameters(
                params=[
                    m.Param(
                        name=m.Name(value="a"),
                        annotation=m.Annotation(annotation=m.Name(value="str")),
                    ),
                    m.Param(
                        name=m.Name(value="b"),
                        annotation=m.Annotation(annotation=m.Name(value="int")),
                    ),
                    m.Param(
                        name=m.Name(value="c"),
                        annotation=m.Annotation(annotation=m.Name(value="str")),
                    ),
                ]
            ),
        ),
    )

    METHOD_MATCHERS = (
        m.FunctionDef(
            name=m.Name(value="__init__"),
            params=m.Parameters(
                params=[
                    m.Param(name=m.Name(value="self")),
                    m.Param(
                        name=m.Name(value="a"),
                        annotation=m.Annotation(annotation=m.Name(value="int")),
                    ),
                ]
            ),
        ),
        m.FunctionDef(
            name=m.Name(value="method"),
            params=m.Parameters(
                params=[
                    m.Param(name=m.Name(value="self")),
                    m.Param(
                        name=m.Name(value="a"),
                        annotation=m.Annotation(annotation=m.Name(value="int")),
                    ),
                    m.Param(
                        name=m.Name(value="b"),
                        annotation=m.Annotation(annotation=m.Name(value="str")),
                    ),
                    m.Param(
                        name=m.Name(value="c"),
                        annotation=m.Annotation(annotation=m.Name(value="int")),
                    ),
                ]
            ),
        ),
        m.FunctionDef(
            name=m.Name(value="multiline_method"),
            params=m.Parameters(
                params=[
                    m.Param(name=m.Name(value="self")),
                    m.Param(
                        name=m.Name(value="a"),
                        annotation=m.Annotation(annotation=m.Name(value="str")),
                    ),
                    m.Param(
                        name=m.Name(value="b"),
                        annotation=m.Annotation(annotation=m.Name(value="int")),
                    ),
                    m.Param(
                        name=m.Name(value="c"),
                        annotation=m.Annotation(annotation=m.Name(value="str")),
                    ),
                ]
            ),
        ),
        m.FunctionDef(
            name=m.Name(value="function"),
            params=m.Parameters(
                params=[
                    m.Param(name=m.Name(value="self")),
                    m.Param(
                        name=m.Name(value="a"),
                        annotation=m.Annotation(annotation=m.Name(value="A")),
                    ),
                    m.Param(
                        name=m.Name(value="b"),
                        annotation=m.Annotation(annotation=m.Name(value="B")),
                    ),
                    m.Param(
                        name=m.Name(value="c"),
                        annotation=m.Annotation(annotation=m.Name(value="C")),
                    ),
                ]
            ),
        ),
    )

    def visit_FunctionDef(self, node: cst.FunctionDef) -> None:
        match scope := self.get_metadata(metadata.ScopeProvider, node):
            # Function
            case metadata.GlobalScope():
                assert any(
                    m.matches(node, fm) for fm in ParameterHintChecker.FUNCTION_MATCHERS
                ), f"{self.__class__.__name__} - Failed to match function `{node.name.value}`"

            case metadata.ClassScope():
                assert any(
                    m.matches(node, fm) for fm in ParameterHintChecker.METHOD_MATCHERS
                ), f"{self.__class__.__name__} - Failed to match method `{node.name.value}`"

            case _:
                assert False, f"Unexpected scope: {scope.__class__.__name__}"


class ReturnHintChecker(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (metadata.ScopeProvider,)

    FUNCTION_MATCHERS = (
        m.FunctionDef(
            name=m.Name("function"),
            returns=m.Annotation(annotation=m.Name(value="int")),
        ),
        m.FunctionDef(
            name=m.Name("function_with_multiline_parameters"),
            returns=m.Annotation(annotation=m.Name(value="int")),
        ),
    )

    METHOD_MATCHERS = (
        m.FunctionDef(
            name=m.Name("__init__"),
            returns=m.Annotation(annotation=m.Name(value="None")),
        ),
        m.FunctionDef(
            name=m.Name("method"),
            returns=m.Annotation(annotation=m.Name(value="tuple")),
        ),
        m.FunctionDef(
            name=m.Name("multiline_method"),
            returns=m.Annotation(annotation=m.Name(value="tuple")),
        ),
        m.FunctionDef(
            name=m.Name("function"),
            returns=m.Annotation(annotation=m.Name(value="int")),
        ),
    )

    def visit_FunctionDef(self, node: cst.FunctionDef) -> None:
        match scope := self.get_metadata(metadata.ScopeProvider, node):
            # Function
            case metadata.GlobalScope():
                assert any(
                    m.matches(node, fm) for fm in ReturnHintChecker.FUNCTION_MATCHERS
                ), f"{self.__class__.__name__} - Failed to match function `{node.name.value}`"

            # Method
            case metadata.ClassScope():
                assert any(
                    m.matches(node, fm) for fm in ReturnHintChecker.METHOD_MATCHERS
                ), f"{self.__class__.__name__} - Failed to match method `{node.name.value}`"

            case _:
                assert False, f"Unexpected scope: {scope.__class__.__name__}"


class AssignHintChecker(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (metadata.ScopeProvider,)

    V_MATCHER = m.AnnAssign(
        target=m.Name(value="v"),
        annotation=m.Annotation(m.Name(value=str.__name__)),
        value=m.FormattedString(),
    )
    # Class annotations are moved to the head of the class
    TYPED_ATTR_A_MATCHER = m.AnnAssign(
        target=m.Attribute(value=m.Name("self"), attr=m.Name("a")),
        annotation=m.Annotation(m.Name(value=int.__name__)),
        value=m.Name(value="a"),
    )
    ATTR_A_MATCHER = m.Assign(
        targets=[m.AssignTarget(m.Attribute(value=m.Name("self"), attr=m.Name("a")))],
        value=m.Name(value="a"),
    )
    ATTR_A_HINT_MATCHER = m.AnnAssign(
        target=m.Name(value="a"),
        annotation=m.Annotation(m.Name(value=int.__name__)),
    )
    A_MATCHER = m.AnnAssign(
        target=m.Name(value="a"),
        annotation=m.Annotation(m.Name(value=int.__name__)),
        value=m.Integer("5"),
    )
    E_MATCHER = m.AnnAssign(
        target=m.Name(value="e"),
        annotation=m.Annotation(m.Name(value=int.__name__)),
        value=None,
    )
    Z_MATCHER = m.AnnAssign(
        target=m.Name(value="z"),
        annotation=m.Annotation(m.Name(value=str.__name__)),
        value=None,
    )
    P_MATCHER = m.AnnAssign(
        target=m.Name(value="p"),
        annotation=m.Annotation(m.Name(value=int.__name__)),
        value=None,
    )
    ZEE_MATCHER = m.AnnAssign(
        target=m.Name(value="zee"),
        annotation=m.Annotation(m.Name(value=bytes.__name__)),
        value=None,
    )
    CLAZZ_MATCHER = m.AnnAssign(
        target=m.Name(value="clazz"),
        annotation=m.Annotation(m.Name(value="Clazz")),
        value=None,
    )

    def visit_AnnAssign(self, node: cst.AnnAssign) -> bool | None:
        self.get_metadata(metadata.ScopeProvider, node) is metadata.GlobalScope()
        assert m.matches(
            node,
            AssignHintChecker.V_MATCHER
            | AssignHintChecker.A_MATCHER
            | AssignHintChecker.TYPED_ATTR_A_MATCHER
            | AssignHintChecker.ATTR_A_HINT_MATCHER
            | AssignHintChecker.E_MATCHER
            | AssignHintChecker.Z_MATCHER
            | AssignHintChecker.P_MATCHER
            | AssignHintChecker.ZEE_MATCHER
            | AssignHintChecker.CLAZZ_MATCHER,
        ), f"Could not match {cst.Module([]).code_for_node(node)}"

        return True

    def visit_Assign(self, node: cst.Assign) -> bool | None:
        if len(node.targets) != 1:
            return False

        elif any(m.matches(target, m.AssignTarget(target=m.Tuple())) for target in node.targets):
            return False

        if m.matches(node, AssignHintChecker.ATTR_A_MATCHER):
            return False

        raise AssertionError(f"Found unannotated Assign!: {cst.Module([]).code_for_node(node)}")
