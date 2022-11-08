import libcst as cst
import pathlib
from typegen.strats.gen import TypeHintGenerator
from typegen.strats.inline import InlineGenerator
from tests.typegen.strats._sample_data import get_test_data
import pandas as pd

import difflib


def load_cst_module(path: pathlib.Path) -> cst.Module:
    module = cst.parse_module(source=path.open().read())
    return module


def test_factory():
    gen = TypeHintGenerator(ident=InlineGenerator.ident, types=pd.DataFrame())
    assert (
        type(gen) is InlineGenerator
    ), f"{type(gen)} should be {InlineGenerator.__name__}"


def test_inline_generator_generates_expected_content(get_test_data):
    for test_element in get_test_data:
        resource_path = test_element[0]
        sample_trace_data = test_element[1]
        expected_inline_content = test_element[2]
        assert resource_path.is_file()

        gen = TypeHintGenerator(ident=InlineGenerator.ident, types=pd.DataFrame())
        hinted = gen._gen_hinted_ast(
            applicable=sample_trace_data, module=load_cst_module(resource_path)
        )
        actual_file_content = hinted.code
        if actual_file_content != expected_inline_content:
            print(f"Test failed for: {str(resource_path)}")
            print(
                "".join(
                    difflib.unified_diff(
                        expected_inline_content.splitlines(1),
                        actual_file_content.splitlines(1),
                    )
                )
            )
            assert False
