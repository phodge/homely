from homely._ui import note
import os
import re
from typing import NamedTuple, Optional

import homely._vcs
from homely._errors import ConnectionError, RepoError, RepoHasNoCommitsError
from homely._ui import warn
from homely._utils import _expandpath, run
from homely.system import execute


class SubmoduleInfo(NamedTuple):
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
    # path of parent submodule, or None if top-level
    parent: Optional[str]


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

        if submodules:
            # collect info on submodules before we make any changes to the main
            # repository - we need to determine which ones are already checked
            # out at the expected commit *before* we do anything
            submodule_states = self._get_submodule_info()
        else:
            submodule_states = []

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
            # NOTE: we need to do another run of _get_submodule_info() because
            # the 'git pull' on the parent repo may have uncovered new
            # submodules we need to fetch
            submodule_states.extend(self._get_submodule_info(skip={i.path for i in submodule_states}))

            self._update_submodules(
                submodule_states,
                done=set(),
                aborted=set(),
            )

    def _update_submodules(
        self,
        submodule_states: list[SubmoduleInfo],
        *,
        done: set[str],
        aborted: set[str],
    ) -> None:
        postponed: list[SubmoduleInfo] = []
        for info in submodule_states:
            # check if the parent submodule is done/aborted first
            if info.parent:
                if info.parent in aborted:
                    note("Submodule '{}' also could not be updated because its parent submodule did not update")
                    aborted.add(info.path)
                    continue

                if info.parent not in done:
                    postponed.append(info)
                    continue

            if not info.is_initialised:
                # not initialized yet
                if info.parent:
                    cwd = os.path.join(self.repo_path, info.parent)
                    relpath = info.path[len(info.parent) + 1:]
                else:
                    cwd = self.repo_path
                    relpath = info.path
                execute(
                    ['git', 'submodule', 'update', '--init', '--recursive', relpath],
                    cwd=cwd,
                )
                done.add(info.path)
                continue

            if info.has_merge_conflicts:
                warn(
                    f"Submodule '{info.path}' indicates merge conflicts"
                    f" (see 'git submodule status'), skipping submodule update"
                )
                aborted.add(info.path)
                continue

            # find out what the expected commit is for this submodule
            expected_sha = self._get_expected_submodule_sha(info.path, info.parent)

            if info.current_sha == expected_sha:
                note(f"Submodule '{info.path}' is already at expected commit {expected_sha[:8]}")
                done.add(info.path)
                continue

            if info.has_moved_commit:
                warn(
                    f"Submodule '{info.path}' has had commit {info.current_sha[:8]} checked out manually"
                    f"; can't move to commit {expected_sha[:8]}"
                )
                aborted.add(info.path)
                continue

            # update submodule to expected commit
            note(f"Updating submodule '{info.path}': {info.current_sha[:8]}...{expected_sha[:8]}")
            returncode = execute(
                ['git', 'checkout', expected_sha],
                cwd=os.path.join(self.repo_path, info.path),
                expectexit=(0, 1),
            )[0]
            if returncode == 0:
                # we need to look for NEW submodules with info.path as parent
                postponed.extend(self._get_submodule_info(
                    only_children_of=info.path,
                    skip={i.path for i in submodule_states},
                ))
                done.add(info.path)
            else:
                warn(
                    f"Failed to update submodule '{info.path}' to commit {expected_sha[:8]} (exit code {returncode})"
                )
                aborted.add(info.path)

        assert len(postponed) < len(submodule_states)
        if postponed:
            self._update_submodules(
                postponed,
                done=done,
                aborted=aborted,
            )

    def _get_submodule_info(
        self,
        skip: set[str] | None = None,
        only_children_of: str = "",
    ) -> list[SubmoduleInfo]:
        if not skip:
            skip = set()

        cmd = ['git', 'submodule', 'status', '--recursive']
        out = execute(
            cmd,
            cwd=self.repo_path,
            stdout=True,
            expectexit=0,
        )[1]
        result = []
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

            if path in skip:
                continue

            # Find the immediate parent submodule (longest matching prefix).
            # We can't just take the first match from the set because
            # iteration order is non-deterministic.
            parent = ""
            for possible_parent in seen:
                if path.startswith(possible_parent + '/'):
                    if len(possible_parent) > len(parent):
                        # prefer a longer parent
                        parent = possible_parent

            if only_children_of and parent != only_children_of:
                continue

            result.append(SubmoduleInfo(
                is_initialised=is_initialised,
                has_merge_conflicts=has_merge_conflicts,
                has_moved_commit=has_moved_commit,
                current_sha=sha,
                path=path,
                parent=parent or None,
            ))
        return result

    def _get_expected_submodule_sha(self, submodule_path: str, parent: str | None) -> str:
        if parent:
            # For nested submodules, rev-parse must run inside the parent
            # submodule's working tree because git can't dereference through
            # a gitlink boundary from the top-level repo.
            cwd = os.path.join(self.repo_path, parent)
            relative_path = submodule_path[len(parent) + 1:]
        else:
            cwd = self.repo_path
            relative_path = submodule_path
        cmd = ['git', 'rev-parse', 'HEAD:' + relative_path]
        out = execute(cmd, cwd=cwd, stdout=True, expectexit=0)[1]
        return out.decode('utf-8').strip()

    def clonetopath(self, dest: str, submodules: bool) -> None:
        origin = self.repo_path
        cmd = ['git', 'clone']
        if submodules:
            cmd.append('--recurse-submodules')
        execute(cmd + [origin, dest])

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
