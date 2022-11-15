import logging
import pathlib
import sys

import libcst.codemod as codemod

from tracing import Tracer

from typegen.strategy import AnnotationGenStratApplier
from typegen.strategy.inline import BruteInlineGenerator
from typegen.strategy.hinter import LibCSTTypeHintApplier
from tests.helpers import paths

from . import driver


def test_main():
    logger = logging.getLogger("integration")

    driver_path = pathlib.Path("tests", "integration", "driver.py")
    tracer = Tracer(
        proj_path=paths.PROJ_PATH, stdlib_path=paths.STDLIB_PATH, venv_path=paths.VENV_PATH
    )
    with tracer.active_trace():
        driver.function(1, "2", 23)
        driver.function_with_multiline_parameters("4", 5, "6")

        clazz = driver.Clazz(1)
        clazz.method(2, 3, 4)
        clazz.multiline_method("Hello", 7, "World")
        clazz.function(a=driver.A(), b=driver.B(), c=driver.C())

    assert tracer.trace_data is not None
    assert not tracer.trace_data.empty

    result = codemod.parallel_exec_transform_with_prettyprint(
        transform=AnnotationGenStratApplier(
            context=codemod.CodemodContext(),
            generator_strategy=BruteInlineGenerator,
            annotation_provider=LibCSTTypeHintApplier,
            traced=tracer.trace_data,
        ),
        files=[str(driver_path)],
        unified_diff=1,
        jobs=1,
        blacklist_patterns=["__init__.py"],
        repo_root=str(paths.PROJ_PATH),
    )

    logger.info(f"Finished codemodding {result.successes + result.skips + result.failures} files!")
    logger.info(f" - Transformed {result.successes} files successfully.")
    logger.info(f" - Skipped {result.skips} files.")
    logger.info(f" - Failed to codemod {result.failures} files.")
    logger.info(f" - {result.warnings} warnings were generated.")
