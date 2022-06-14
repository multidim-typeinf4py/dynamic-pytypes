from abc import ABC, abstractmethod

import requests
import pathlib
import tempfile
import shutil

from .projio import Project

import git


class Repository(ABC):
    def __init__(self, project_url: str):
        self.project_url = project_url

    def fetch(self, output: pathlib.Path) -> Project:
        """
        Download the project from the URL specified in the constructor
        and store it in the path specified by output 
        """
        td = self._fetch()
        self._write_to(td, output)

        return Project(output)

    @property
    @abstractmethod
    def fmt(self) -> str:
        """
        Static attribute indicating format of repository
        """
        pass

    @abstractmethod
    def _fetch(self) -> tempfile.TemporaryDirectory:
        """
        Fetch the project at the specified URL, and store it under a temporary directory
        """
        pass

    def _write_to(
        self, intermediary: tempfile.TemporaryDirectory, output: pathlib.Path
    ):
        output.mkdir(parents=True, exist_ok=True)

        inter_path = pathlib.Path(intermediary.name)
        for inpath in inter_path.iterdir():
            relpath = inpath.relative_to(inter_path)
            outpath = output / relpath

            shutil.move(inpath, outpath)


class GitRepository(Repository):
    def __init__(self, project_url: str):
        super().__init__(project_url)

    fmt = "Git"

    def _fetch(self) -> tempfile.TemporaryDirectory:
        td = tempfile.TemporaryDirectory()
        git.Repo.clone_from(self.project_url, td.name)
        return td


class ArchiveRepository(Repository):
    def __init__(self, project_url: str):
        super().__init__(project_url)

    fmt = "Archive"

    def _fetch(self) -> tempfile.TemporaryDirectory:
        td = tempfile.TemporaryDirectory()
        git.Repo.clone_from(self.project_url, td.name)
        return td


def repository_factory(project_url: str, fmt: str | None) -> Repository:
    if fmt == GitRepository.fmt or project_url.endswith(".git"):
        return GitRepository(project_url)

    if fmt == ArchiveRepository.fmt or project_url.endswith((".tar.gz", ".zip")):
        return ArchiveRepository(project_url)

    raise LookupError(f"Unsupported repository format: {project_url}")
