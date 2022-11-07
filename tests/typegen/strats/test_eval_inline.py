import difflib
import libcst as cst
import pathlib
from typegen.strats.gen import TypeHintGenerator
from typegen.strats.eval_inline import EvaluationInlineGenerator
from tests.typegen.strats._sample_data import get_test_data
import pandas as pd


def load_cst_module(path: pathlib.Path) -> cst.Module:
    module = cst.parse_module(source=path.open().read())
    return module


def test_factory():
    gen = TypeHintGenerator(ident=EvaluationInlineGenerator.ident, types=pd.DataFrame())
    assert (
        type(gen) is EvaluationInlineGenerator
    ), f"{type(gen)} should be {EvaluationInlineGenerator.__name__}"


def test_inline_generator_generates_expected_content(get_test_data):
    for (
        resource_path,
        sample_trace_data,
        _,
        expected_eval_inline_content,
        *_
    ) in get_test_data:
        assert resource_path.is_file()

        print(f"Working on {resource_path}")

        gen = TypeHintGenerator(
            ident=EvaluationInlineGenerator.ident, types=pd.DataFrame()
        )
        hinted = gen._gen_hinted_ast(
            applicable=sample_trace_data, module=load_cst_module(resource_path)
        )
        actual_file_content = hinted.code
        if actual_file_content != expected_eval_inline_content:
            print(f"Test failed for: {str(resource_path)}")

            diff = "".join(
                difflib.unified_diff(
                    expected_eval_inline_content.splitlines(1),
                    actual_file_content.splitlines(1),
                )
            )
            print(f"Diff: {diff}")

            assert False
