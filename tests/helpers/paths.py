import os
import pathlib

PROJ_PATH = pathlib.Path.cwd()
STDLIB_PATH = pathlib.Path(pathlib.__file__).parent
VENV_PATH = pathlib.Path(os.environ["VIRTUAL_ENV"])
