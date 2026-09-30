import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import homely._vcs
from homely._errors import ConnectionError, RepoError, RepoHasNoCommitsError
from homely._ui import note, warn
from homely._utils import _expandpath, run
from homely.system import execute


@dataclass
class SubmoduleInfo:
    # TODO: ditch all of this comments since we no longer have a 'status' column
    # One of ' ', '-', '+', 'U', or '' if the status character is unrecognized
    #   '-': submodule is not yet initialised
    #   '+': submodule is intialised but has been moved to a different commit than the one specified in the index.
    #        NOTE: this is often incorrect for a sub-submodule if we haven't
    #        yet moved the parent submodule to the correct commit.
    #   'U': submodule has merge conflicts
    #   ' ': submodule is OK to move? Kind of - if there are uncommitted
    #        changes we want to be careful about how we check out the new
    #        commit. Actually ... no I think we can just do a manual "git checkout"
    #        for each submodule.
    #        Note that when you're moving a submodule that has its own
    #        sub-submodule, if the sub-submodule has been moved to another
    #        commit then moving the parent submodule *could* cause the
    #        sub-submodule to match the expected commit without moving it
    #        directly. Also its important to note that for a sub-submodule you
    #        can't know the expected commit until the parent submodule has been
    #        checked out.
    # status: Literal[' ', '-', '+', 'U', '']
    is_initialised: bool
    has_merge_conflicts: bool
    has_moved_commit: bool
    current_sha: str
    path: str
    full_path: str
    removed_from_parent: bool

    def is_dirty(self) -> bool:
        raise Exception("TODO: get the old implmeentation plz")  # noqa


class Repo(homely._vcs.Repo):
    type_ = homely._vcs.RepoType.HANDLER_GIT_v1
    pulldesc = 'git pull'

    @classmethod
    def _from_parts(class_, repo_path: str, user: str, domain: str, name: str) -> "Repo":
        if name.endswith('.git'):
            name = name[0:-4]

        canonical = 'https://%s/%s/%s.git' % (domain, user, name)

        return class_(
            repo_path,
            isremote=True,
            iscanonical=repo_path == canonical,
            canonical=canonical,
            suggestedlocal=name,
        )

    @classmethod
    def frompath(class_, repo_path: str) -> Optional["Repo"]:
        if os.path.isdir(repo_path):
            if not os.path.isdir(os.path.join(repo_path, '.git')):
                return None

            return class_(_expandpath(repo_path),
                          isremote=False,
                          iscanonical=False,
                          suggestedlocal=None
                          )

        if (repo_path.startswith('ssh://') or
                repo_path.startswith('https://') or
                repo_path.startswith('git@')):

            # handle git@ url
            m = re.match(r'^git@([^/]+)[/:]([^/]+)/([^/]+)', repo_path)
            if m:
                domain, user, name = m.groups()
                return class_._from_parts(repo_path, user=user, domain=domain, name=name)

            # TODO: gitlab allows '/' in the org name so we actually want all but the last '/part'
            # to be the 'user'
            m = re.match(r'^https://([^/]+)/([^/]+)/([^/]+)', repo_path)
            if m:
                domain, user, name = m.groups()
                return class_._from_parts(repo_path, user=user, domain=domain, name=name)

            return class_(repo_path,
                          isremote=True,
                          iscanonical=False,
                          suggestedlocal=None)

        return None

    def pullchanges(self, submodules: bool = False) -> None:
        assert not self.isremote

        submodule_states: dict[str, SubmoduleInfo] = {}

        if submodules:
            # collect info on submodules before we make any changes to the main
            # repository - we need to determine which ones are already checked
            # out at the expected commit *before* we do anything
            _refresh_submodule_info(Path(self.repo_path), submodule_states, path_from_root=[])

        code, _, err = execute(['git', 'pull'],
                               cwd=self.repo_path,
                               stderr=True,
                               expectexit=(0, 1))
        if code != 0:
            assert isinstance(err, bytes)  # TODO: replace this with a type check
            needle = b'fatal: Could not read from remote repository.'
            if needle in err:
                raise ConnectionError()

            raise SystemError(
                f"Unexpected failure of 'git pull': exit({code}) {err!r}"
            )

        if submodules:
            # NOTE: we need to do another run of _refresh_submodule_info() because
            # the 'git pull' on the parent repo may have uncovered that we now
            # need to add new submodules or remove others
            _refresh_submodule_info(Path(self.repo_path), submodule_states, path_from_root=[])

            _update_submodules_recursively(
                parent_path=Path(self.repo_path),
                submodule_states=submodule_states,
                path_from_root=[],
            )

    def clonetopath(self, dest: str, submodules: bool) -> None:
        origin = self.repo_path
        cmd = ['git', 'clone']
        if submodules:
            cmd.append('--recurse-submodules')
        execute(cmd + [origin, dest])

        # TODO: why did we use 'git submodule update --init --recursive instead???'
        if submodules and False:
            execute(['git', 'submodule', 'update', '--init', '--recursive'], cwd=dest)

    def getrepoid(self) -> str:
        assert not self.isremote
        cmd = ['git', 'rev-list', '--max-parents=0', 'HEAD']
        returncode, stdout = run(cmd,
                                 cwd=self.repo_path,
                                 stdout=True,
                                 stderr="STDOUT")[:2]
        assert isinstance(stdout, bytes)  # TODO: replace this with a type check
        if returncode == 0:
            return self._getfirsthash(stdout)
        if returncode != 128:
            raise Exception("Unexpected returncode {} from git rev-list"
                            .format(returncode))

        if b"ambiguous argument 'HEAD'" not in stdout:
            raise Exception("Unexpected exitcode {}".format(returncode))

        # there's no HEAD revision, so we'll do the command again with
        # --all instead
        cmd = ['git', 'rev-list', '--max-parents=0', '--all']
        # use run() instead of execute() so that we don't print script output
        returncode, stdout = run(cmd,
                                 cwd=self.repo_path,
                                 stdout=True,
                                 stderr="STDOUT")[:2]
        if returncode == 0:
            if stdout == b'':
                raise RepoHasNoCommitsError()
            return self._getfirsthash(stdout)
        if returncode != 129:
            raise Exception("Unexpected returncode {} from git rev-list"
                            .format(returncode))
        if b"usage: git rev-list" in stdout:
            raise RepoHasNoCommitsError()

        raise SystemError("Unexpected exitcode {}".format(returncode))

    def _getfirsthash(self, stdout: bytes) -> str:
        stripped = stdout.rstrip().decode('utf-8')
        if '\n' in stripped:
            raise RepoError("Git repo has multiple initial commits")
        return stripped

    @staticmethod
    def shortid(repoid: str) -> str:
        return repoid[0:8]

    def isdirty(self) -> bool:
        cmd = ['git', 'status', '--porcelain']
        out = execute(cmd, cwd=self.repo_path, stdout=True)[1]
        assert isinstance(out, bytes)  # TODO: replace this with a type check
        for line in out.split(b'\n'):
            if len(line) and not line.startswith(b'?? '):
                return True
        return False


def _refresh_submodule_info(
    parent_path: Path,
    store: dict[str, SubmoduleInfo],
    *,
    path_from_root: list[str],
) -> None:
    out = execute(
        ['git', 'submodule', 'status'],
        cwd=parent_path,
        stdout=True,
        expectexit=0,
    )[1]
    seen: set[str] = set()
    for line in out.decode('utf-8').splitlines():
        if not line.strip():
            continue

        # format: [-+U ]<sha> <path> [(<describe>)]
        status_char = line[0]
        rest = line[1:]
        parts = rest.strip().split(' ', 2)
        sha = parts[0]
        path = parts[1]
        is_initialised = True
        has_merge_conflicts = False
        has_moved_commit = False
        if status_char == '-':
            is_initialised = False
        elif status_char == 'U':
            has_merge_conflicts = True
        elif status_char == '+':
            has_moved_commit = True
        elif status_char not in ' +':
            warn(f"Unexpected status character '{status_char}' in git submodule status output")
            continue

        seen.add(path)

        if path not in store:
            store[path] = SubmoduleInfo(
                is_initialised=is_initialised,
                has_merge_conflicts=has_merge_conflicts,
                has_moved_commit=has_moved_commit,
                current_sha=sha,
                path=path,
                full_path="/".join(path_from_root + [path]),
                removed_from_parent=False,
            )

    # mark removed submodules
    for path in store:
        if path not in seen:
            store[path].removed_from_parent = True


def _update_submodules_recursively(
    parent_path: Path,
    submodule_states: dict[str, SubmoduleInfo],
    path_from_root: list[str],
) -> None:
    for info in submodule_states.values():
        # find out if the submodule itself has any of its own submodules
        sub_submodules: dict[str, SubmoduleInfo] = {}
        if info.is_initialised:
            _refresh_submodule_info(parent_path / info.path, sub_submodules, path_from_root=path_from_root + [info.path])

        if info.has_merge_conflicts:
            warn(
                f"Submodule '{info.path}' indicates merge conflicts"
                f" (see 'git submodule status'), skipping submodule update"
            )
            continue

        if not info.is_initialised:
            # just need to initialise the submodule (and all its descendants)
            execute(
                ['git', 'submodule', 'update', '--init', '--recursive', info.path],
                cwd=parent_path,
            )
            continue

        if info.removed_from_parent:
            if _issue_submodule_removal_warning(info, sub_submodules):
                # if a warning was issued, we can't clean up this submodule at this stage
                continue

            raise Exception("TODO: deal with submodule that needs to be gooone")  # noqa

        # find out what the expected commit is for this submodule
        expected_sha = _get_expected_submodule_sha(parent_path, info.path)

        if info.current_sha == expected_sha:
            note(f"Submodule '{info.path}' is already at expected commit {expected_sha[:8]}")
            continue

        if info.has_moved_commit:
            warn(
                f"Submodule '{info.path}' has had commit {info.current_sha[:8]} checked out manually"
                f"; can't move to commit {expected_sha[:8]}"
            )
            continue

        # update submodule to expected commit
        note(f"Updating submodule '{info.path}': {info.current_sha[:8]}...{expected_sha[:8]}")
        # For nested submodules, `git submodule update` must run inside
        # the parent submodule's working tree with a relative path.
        #if info.parent is not None:
            #cwd = os.path.join(self.repo_path, info.parent)
            #relative_path = info.path[len(info.parent) + 1:]
        #else:
            #cwd = self.repo_path
            #relative_path = info.path
        # TODO: explain why we're using 'git checkout $SHA' instead of 'git submodule update':
        # Use 'git checkout $SHA' instead of the simpler 'git submodule update' for the following reasons:
        # - Won't attempt to recurse into sub-submodules
        # - Will more?????
        # the parent submodule is at the wrong commit, because it tries to
        # check out the nested submodule at the expected commit before
        # moving the parent submodule to the expected commit, and this
        # causes it to fail with "fatal: reference is not a tree" (because
        # the expected commit for the nested submodule doesn't exist in the
        # current commit of the parent submodule).
        returncode = execute(
            #['git', 'submodule', 'update', relative_path],
            #cwd=cwd,
            ['git', 'checkout', expected_sha],
            cwd=parent_path / info.path,
            expectexit=(0, 1),
        )[0]
        if returncode != 0:
            warn(
                f"Failed to update submodule '{info.path}' to commit {expected_sha[:8]} (exit code {returncode})"
            )
            continue

        # look for any changes relating to sub-submodules of this submodule
        _refresh_submodule_info(
            parent_path / info.path,
            sub_submodules,
            path_from_root=path_from_root + [info.path],
        )

        # now we can recursively update sub-submodules of this submodule
        _update_submodules_recursively(
            parent_path=parent_path / info.path,
            submodule_states=sub_submodules,
            path_from_root=path_from_root + [info.path],
        )


def _get_expected_submodule_sha(parent_path: Path, submodule_path: str) -> str:
    out = execute(
        ['git', 'rev-parse', 'HEAD:' + submodule_path],
        cwd=parent_path,
        stdout=True,
        expectexit=0,
    )[1]
    return out.decode('utf-8').strip()


def _issue_submodule_removal_warning(info: SubmoduleInfo, sub_submodules: dict[str, SubmoduleInfo]) -> bool:
    def _warn(reason: str) -> None:
        warn(
            f"Submodule '{info.full_path}' is no longer tracked as a submodule but can't be removed because {reason}"
        )

    if info.has_moved_commit:
        _warn(f"commit {info.current_sha[:8]} was either checked out manually or created locally")
        return True

    if info.is_dirty():
        _warn("it has local changes that haven't been committed")
        return True

    # do any of the submodules sub-submodules prevent its removal?
    for sub_info in sub_submodules.values():
        raise Exception("TODO: check each sub-subvmodule as well")  # noqa

    # no reason it can't be removed
    return False
