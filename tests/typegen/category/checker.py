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
