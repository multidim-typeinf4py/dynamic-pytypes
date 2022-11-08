import libcst as cst
import libcst.metadata as metadata
import libcst.matchers as m

import textwrap

import pytest


@pytest.fixture
def typed() -> metadata.MetadataWrapper:
    text = textwrap.dedent(
        """
def function(a: int, b: str, c: int) -> int:
    v: str = f'{a}{b}{c}'
    return int(v)

def function_with_multiline_parameters(
    a: str,
    b: int,
    c: str
) -> int:
    v: str = f'{a}{b}{c}'
    return int(v)

class Clazz:
    def method(self, a: int, b: str, c: int) -> tuple[int, str, int]:
        return a, b, c

    def multiline_method(
        self, 
        a: str, 
        b: int, 
        c: str
    ) -> tuple[str, int, str]:
        return a, b, c

    def function(self, a: A, b: B, c: C) -> int:
        v: str = f'{a}{b}{c}'
        return int(v)
    """
    )

    module = cst.parse_module(text)
    return metadata.MetadataWrapper(module)


class ParameterHintRemover(cst.CSTTransformer):
    def leave_Param(self, _: cst.Param, updated_node: cst.Param) -> cst.Param:
        return updated_node.with_changes(annotation=None)


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

    def visit_FunctionDef(self, node: cst.FunctionDef) -> bool:
        scope = self.get_metadata(metadata.ScopeProvider, node)
        print(type(scope))

        # Function
        if isinstance(scope, metadata.GlobalScope):
            assert any(
                m.matches(node, fm) for fm in ParameterHintChecker.FUNCTION_MATCHERS
            ), f"{ParameterHintChecker.__name__} - Failed to match function `{node.name.value}`"

        # Method
        elif isinstance(scope, metadata.ClassScope):
            assert any(
                m.matches(node, fm) for fm in ParameterHintChecker.METHOD_MATCHERS
            ), f"{ParameterHintChecker.__name__} - Failed to match method `{node.name.value}`"

        return False


class ReturnHintChecker(cst.CSTVisitor):
    FUNCTION_MATCHERS = (
        m.FunctionDef(
            name="function", returns=m.Annotation(annotation=m.Name(value="int"))
        ),
        m.FunctionDef(
            name="function_with_multiline_parameters",
            returns=m.Annotation(annotation=m.Name(value="int")),
        ),
    )

    METHOD_MATCHERS = (
        m.FunctionDef(
            name="method",
            returns=m.Annotation(
                annotation=m.Subscript(
                    value=m.Name("tuple"),
                    slice=[
                        m.SubscriptElement(slice=m.Index(value=m.Name(ty)))
                        for ty in ("int", "str", "int")
                    ],
                )
            ),
        ),
        m.FunctionDef(
            name="multiline_method",
            returns=m.Annotation(
                annotation=m.Subscript(
                    value=m.Name("tuple"),
                    slice=[
                        m.SubscriptElement(slice=m.Index(value=m.Name(t)))
                        for t in ("str", "int", "str")
                    ],
                )
            ),
        ),
        m.FunctionDef(
            name="function", returns=m.Annotation(annotation=m.Name(value="int"))
        ),
    )
