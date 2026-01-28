import os
from enum import Enum
from typing import Iterable, Optional

from homely._errors import NotARepo

_handlers = None


class RepoType(Enum):
    HANDLER_GIT_v1 = "vcs:git"
    HANDLER_TESTHANDLER_v1 = "vcs:testhandler"


def _gethandlers() -> Iterable[type["Repo"]]:
    global _handlers
    import homely._vcs.git
    import homely._vcs.testhandler
    _handlers = [
        homely._vcs.git.Repo,
        homely._vcs.testhandler.Repo,
    ]
    return _handlers


def getrepohandler(repo_path: str) -> "Repo":
    for class_ in _handlers or _gethandlers():
        repo = class_.frompath(repo_path)
        if repo is not None:
            return repo
    raise NotARepo(repo_path)


def fromdict(row: dict[str, str | bool]) -> "Repo":
    for class_ in _handlers or _gethandlers():
        obj = class_.fromdict(row)
        if obj is not None:
            return obj
    raise Exception("No Repo handler wants to load %r" % row)


class Repo:
    """
    Base class for VCS handlers
    """
    type_: RepoType

    def __init__(
        self,
        repo_path: str,
        isremote: bool,
        iscanonical: bool,
        suggestedlocal: Optional[str],
        canonical: Optional[str] = None,
    ):
        self.isremote = isremote
        self.iscanonical = iscanonical
        self.repo_path = repo_path
        if suggestedlocal is None:
            suggestedlocal = os.path.basename(repo_path)
        self.suggestedlocal = suggestedlocal
        self._canonical = canonical

    @classmethod
    def frompath(class_, repo_path: str) -> Optional["Repo"]:
        raise Exception(
            "%s.%s needs to implement @classmethod .frompath(repo_path)" % (
                class_.__module__, class_.__name__))

    @classmethod
    def shortid(class_, repoid: str) -> str:
        raise Exception(
            "%s.%s needs to implement @staticmethod .shortid(repoid)" % (
                class_.__module__, class_.__name__))

    def getrepoid(self) -> str:
        """
        Get a unique id for the repo. For example, the first commit hash.
        """
        raise Exception(
            "%s.%s needs to implement .getrepoid()" % (
                self.__class__.__module__, self.__class__.__name__))

    def clonetopath(self, dest: str) -> None:
        """
        Clone the repo at <self.pushablepath> into <dest>
        Note that if self.pushablepath is None, then self.path will be used
        instead.
        """
        raise Exception(
            "%s.%s needs to implement @classmethod .clonetopath(dest)" % (
                self.__class__.__module__, self.__class__.__name__))

    def isdirty(self) -> bool:
        raise Exception(
            "%s.%s needs to implement .isdirty()" % (
                self.__class__.__module__, self.__class__.__name__))

    def pullchanges(self) -> None:
        raise Exception(
            "%s.%s needs to implement .pullchanges()" % (
                self.__class__.__module__, self.__class__.__name__))

    def asdict(self) -> dict[str, str | bool]:
        return dict(
            type=self.type_.value,
            repo_path=self.repo_path,
            isremote=self.isremote,
            iscanonical=self.iscanonical,
            suggestedlocal=self.suggestedlocal,
        )

    @classmethod
    def fromdict(class_, row: dict[str, str | bool]) -> Optional["Repo"]:
        if row["type"] != class_.type_.value:
            return None

        assert isinstance(row["repo_path"], str)
        assert isinstance(row["suggestedlocal"], str)
        assert isinstance(row["isremote"], bool)
        assert isinstance(row["iscanonical"], bool)

        return class_(
            row["repo_path"],
            row["isremote"],
            row["iscanonical"],
            row["suggestedlocal"],
        )
