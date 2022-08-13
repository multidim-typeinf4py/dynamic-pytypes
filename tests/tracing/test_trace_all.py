from tracing import decorators
from constants import TraceData


@decorators.register()
def trace_function():
    return f"More"


class Class:
    @decorators.register()
    def trace_method(self):
        return f"Something"


def main():
    ...


def test_everything_is_traced():
    trace_data, _ = decorators.entrypoint(None)(main)
    assert trace_data is not None

    assert "trace_method" in trace_data[TraceData.FUNCNAME].values
    assert "trace_function" in trace_data[TraceData.FUNCNAME].values
