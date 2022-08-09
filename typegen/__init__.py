import logging
import sys

import click
import pathlib

import constants

from tracing import ptconfig

from typegen.strats.gen import TypeHintGenerator
from typegen.trace_data_file_collector import TraceDataFileCollector

from .strats.stub import StubFileGenerator
from .strats.inline import InlineGenerator

__all__ = [
    TraceDataFileCollector.__name__,
]

@click.command(name="typegen", help="Collects trace data files in directories")
@click.option(
    "-p",
    "--path",
    type=click.Path(exists=True, dir_okay=True, writable=False, readable=True, path_type=pathlib.Path),
    help="Path to project directory",
    required=True,
)
@click.option(
    "-s",
    "--subdirs",
    help="Go down the directory tree of the tests, instead of staying in the first level",
    is_flag=True,
    required=False,
    default=True,
)
@click.option(
    "-g",
    "--gen-strat",
    help="Select a strategy for generating type hints",
    type=click.Choice([StubFileGenerator.ident, InlineGenerator.ident], case_sensitive=False),
    required=True,
)
@click.option(
    "-v",
    "--verbose",
    help="INFO if not given, else CRITICAL",
    is_flag=True,
    callback=lambda ctx, _, val: logging.INFO if val else logging.CRITICAL,
    required=False,
    default=False,
)
def main(**params):
    projpath, verb, strat_name, subdirs = (
        params["path"],
        params["verbose"],
        params["gen_strat"],
        params["subdirs"],
    )

    logging.basicConfig(level=verb)
    logging.debug(f"{projpath=}, {verb=}, {strat_name=} {subdirs=}")

    project_root_file = next(pathlib.Path(projpath).rglob("project_root.txt"))
    with project_root_file.open() as f:
        project_roots = f.readlines()
        sys.path.append(project_roots)

    pytypes_cfg = ptconfig._load_config(projpath / constants.CONFIG_FILE_NAME)
    traced_df_folder = pathlib.Path(pytypes_cfg.pytypes.project)

    collector = TraceDataFileCollector()
    collector.collect_trace_data(projpath, subdirs)

    print(collector.trace_data)

    filter_list = TraceDataFilterList()
    filter_list.append(DropTestFunctionDataFilter(test_function_name_pattern=constants.PYTEST_FUNCTION_PATTERN))
    filter_list.append(DropDuplicatesFilter())
    filter_list.append(ReplaceSubTypesFilter(only_replace_if_base_type_already_in_data=True))
    #filter_list.append(DropDuplicatesFilter())
    #filter_list.append(DropVariablesOfMultipleTypesFilter(min_amount_types_to_drop=2))

    processed_data = filter_list.get_processed_data(collector.trace_data)
    print(processed_data)
    return
    hint_generator = TypeHintGenerator(ident=strat_name, types=processed_data)
    hint_generator.apply()
