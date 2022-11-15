import pathlib

from tracing import decorators
from common import ptconfig
from constants import Column


def trace_function():
    return f"More"


class Class:
    def trace_method(self):
        return f"Something"


MOCK_PATH = pathlib.Path("tests", "tracing", "decorators")


def test_everything_is_traced(monkeypatch):
    monkeypatch.setattr(pathlib.Path, pathlib.Path.cwd.__name__, lambda: MOCK_PATH.resolve())
    monkeypatch.setattr(
        ptconfig,
        ptconfig.load_config.__name__,
        lambda _: ptconfig.TomlCfg(
            ptconfig.PyTypes(
                project="standard-trace",
                proj_path=MOCK_PATH.resolve(),
                stdlib_path=pathlib.Path(),
                venv_path=pathlib.Path(),
                benchmark_performance=False,
            )
        ),
    )

    ftrace, fperf = decorators.dev_trace(trace_function)()
    assert fperf is None
    assert ftrace is not None, f"Trace data should not be None"
    assert (
        "trace_function" in ftrace[Column.FUNCNAME].values
    ), f"Trace data for 'trace_function' is missing"

    mtrace, mperf = decorators.dev_trace(Class().trace_method)()
    assert mperf is None
    assert mtrace is not None, f"Trace data should not be None"
    assert (
        Class.trace_method.__qualname__ in mtrace[Column.FUNCNAME].values
    ), f"Trace data for 'trace_method' is missing"


def test_everything_is_traced_with_benchmark_performance(monkeypatch):
    monkeypatch.setattr(pathlib.Path, pathlib.Path.cwd.__name__, lambda: MOCK_PATH.resolve())
    monkeypatch.setattr(
        ptconfig,
        ptconfig.load_config.__name__,
        lambda _: ptconfig.TomlCfg(
            ptconfig.PyTypes(
                project="standard-trace",
                proj_path=MOCK_PATH.resolve(),
                stdlib_path=pathlib.Path(),
                venv_path=pathlib.Path(),
                benchmark_performance=True,
            )
        ),
    )

    ftrace, fperf = decorators.dev_trace(trace_function)()
    assert ftrace is not None, f"Trace data should not be None"
    assert (
        "trace_function" in ftrace[Column.FUNCNAME].values
    ), f"Trace data for 'trace_function' is missing"

    assert fperf is not None, f"When benchmarking, perf data 'fperf': should not be None"
    assert fperf.shape == (4,), f"Wrong benchmark shape for 'fperf': Got {fperf.shape}"

    mtrace, mperf = decorators.dev_trace(Class().trace_method)()
    assert mtrace is not None, f"Trace data should not be None"
    assert (
        Class.trace_method.__qualname__ in mtrace[Column.FUNCNAME].values
    ), f"Trace data for 'trace_method' is missing"

    assert mperf is not None, f"When benchmarking, perf data 'mperf': should not be None"
    assert mperf.shape == (4,), f"Wrong benchmark shape for 'mperf': Got {mperf.shape}"
