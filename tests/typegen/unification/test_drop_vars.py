from typegen.unification.filter_base import TraceDataFilter
from typegen.unification.drop_vars import DropVariablesOfMultipleTypesFilter

from .data import sample_trace_data

from constants import Schema, Column

multi_var_filter = TraceDataFilter(ident=DropVariablesOfMultipleTypesFilter.ident)  # type: ignore


def test_factory():
    assert isinstance(multi_var_filter, DropVariablesOfMultipleTypesFilter)


def test_drop_variables_of_multiple_types_filter_processes_and_returns_correct_data(
    sample_trace_data,
):
    expected_trace_data = sample_trace_data.copy().iloc[[5, 6]].reset_index(drop=True)
    expected_trace_data = expected_trace_data.astype(Schema.TraceData)

    trace_data = sample_trace_data.copy()
    actual_trace_data = multi_var_filter.apply(trace_data)

    assert expected_trace_data.equals(actual_trace_data)
