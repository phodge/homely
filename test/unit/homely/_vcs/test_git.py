import os
import re
import tempfile
from contextlib import _GeneratorContextManager, contextmanager
from pathlib import Path
from subprocess import check_call, check_output
from typing import TYPE_CHECKING, Callable, Iterator

import pytest

# TODO: get rid of this thing
GIT: list[str | os.PathLike] = ['git']

if TYPE_CHECKING:
    from homely._vcs.git import Repo


def path2Repo(path: Path) -> "Repo":
    from homely._vcs.git import Repo

    repo = Repo.frompath(str(path))
    assert repo is not None
    return repo


def makegitrepo(tmpdir: Path, name: str, *, children: list[str] | None = None) -> Path:
    path = tmpdir / name

    def system(cmd: list[str | os.PathLike]) -> None:
        check_call(cmd, cwd=path)

    path.mkdir()
    system(GIT + ['init'])
    # add an initial commit
    readme = path / 'README.md'
    readme.write_text("Hello\n")
    system(GIT + ['add', 'README.md'])
    system(GIT + ['commit', '-m', 'Added readme'])

    # add a 2nd commit
    readme.write_text(f"I am repo {name}\n")
    system(GIT + ['commit', '-m', 'Updated readme', 'README.md'])

    # split children into direct children and grandchildren, so that we can
    # create children repos first along with their grandchildren
    nested_children: dict[str, list[str]] = {}
    for childspecifier in children or []:
        assert '.' not in childspecifier
        childnameparts = childspecifier.split('/', 1)
        childname = childnameparts[0]
        nested_children.setdefault(childname, [])
        if len(childnameparts) > 1:
            nested_children[childname].append(childnameparts[1])

    for childname, subchildren in nested_children.items():
        childpath = makegitrepo(tmpdir, name + '.' + childname, children=subchildren)
        # add the child as a submodule
        system(GIT + ['submodule', 'add', childpath, childname])

    return path


def _register_submodule(parentpath: Path, where: str, submodulepath: Path) -> None:
    check_call(
        GIT + ['submodule', 'add', submodulepath, where],
        cwd=parentpath,
    )
    check_call(
        GIT + ['commit', '-m', f'Added submodule {submodulepath.name}'],
        cwd=parentpath,
    )


def _pull_commit_latest_submodule(
    parent_path: Path,
    submodule_where: str,
    *,
    commitmsg: str = '',
    commitsha: str = '',
) -> None:
    if not commitmsg:
        assert not commitsha
        commitmsg = f'Update to latest version of {submodule_where}'
    check_call(['git', 'submodule', 'update', '--remote', submodule_where], cwd=parent_path)
    if commitsha:
        check_call(['git', 'checkout', commitsha], cwd=parent_path / submodule_where)
    check_call(GIT + ['commit', '-m', commitmsg, submodule_where], cwd=parent_path)


@pytest.fixture(scope='session')
def session_tmpdir() -> Iterator[Path]:
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


WithSubmodulesRoot = Callable[[Path], _GeneratorContextManager[Path, None, None]]


@pytest.fixture(scope='session')
def with_submodules_root() -> Iterator[WithSubmodulesRoot]:
    with tempfile.TemporaryDirectory() as tmpdir:
        symlink_home = Path(tmpdir) / 'submodules'

        @contextmanager
        def _context_manager(temporary_home: Path) -> Iterator[Path]:
            # connect the symlink to the temporary home
            symlink_home.symlink_to(temporary_home)
            yield symlink_home
            symlink_home.unlink()

        yield _context_manager


@pytest.fixture
def ed2sourcepath(tmp_path: Path) -> Iterator[Path]:
    register_submodules: list[tuple[Path, str, Path]] = []

    def wantsubmodule(parentpath: Path, where: str, submodulepath: Path | None = None, *, register=False) -> Path:
        if submodulepath is None:
            tmpdir = parentpath.parent
            whereparts = where.split('/')
            submodulepath = tmpdir / whereparts[-1]
            makegitrepo(tmpdir, whereparts[-1])

        if register:
            _register_submodule(parentpath, where, submodulepath)
        else:
            register_submodules.append((parentpath, where, submodulepath))

        return submodulepath

    # create a parent repo for a cool text editor
    ed2path = makegitrepo(tmp_path, 'ed2')

    # create a couple of submodules for the website and AI models
    ed2websitepath = makegitrepo(tmp_path, 'ed2website')
    wantsubmodule(ed2path, 'www', ed2websitepath)
    wantsubmodule(ed2path, 'extra/ed2models')

    # website will need a submodule also
    wantsubmodule(ed2websitepath, 'assets')

    # create a syntax highlighting submodule that will have submodules of its own
    ed2syntaxpath = wantsubmodule(ed2path, 'extra/ed2syntax')

    # create some syntax submodules for different languages
    wantsubmodule(ed2syntaxpath, 'lang/python')
    wantsubmodule(ed2syntaxpath, 'lang/typescript')
    phpsyntaxpath = wantsubmodule(ed2syntaxpath, 'lang/php')
    # we register the lang/html submodule immediately so that when we later add
    # extensions/css to lang/html, it won't appear in ed2syntax/lang/html/extensions/css
    htmlsyntaxpath = wantsubmodule(ed2syntaxpath, 'lang/html', register=True)

    # also add html syntax as a submodule under the PHP syntax
    wantsubmodule(phpsyntaxpath, 'extensions/html', htmlsyntaxpath)

    # html syntax repo gets a submodule for CSS syntax, but we register it immediately
    wantsubmodule(htmlsyntaxpath, 'extensions/css')

    # register submodules in reverse order to ensure that they each get the
    # latest version of each submodule (except the PHP submodule which we
    # deliberately registered early as mentioned above)
    for parentpath, where, submodulepath in reversed(register_submodules):
        _register_submodule(parentpath, where, submodulepath)

    yield ed2path


def test_git(tmp_path: Path) -> None:
    """
    TODO: phase out this full-lifecycle test in favour of individual tests for clonetopath() and pullchanges()
    """
    # test loading handler from url
    from homely._vcs.git import Repo

    # check that frompath() works on folders also
    assert Repo.frompath(str(tmp_path)) is None

    mygit = tmp_path / 'therepo'
    mygit.mkdir()
    (mygit / '.git').mkdir()
    repo = path2Repo(mygit)
    assert repo.repo_path == mygit
    assert repo.iscanonical is False
    assert repo.isremote is False
    assert repo.pulldesc == 'git pull'

    # test repo.clonetopath() and repo.isdirty()
    fake1path = makegitrepo(tmp_path, 'fake1')
    fake1repo = path2Repo(fake1path)
    assert fake1repo.suggestedlocal == 'fake1'
    assert re.match(r'^[0-9a-f]{40}$', fake1repo.getrepoid())
    assert re.match(r'^[0-9a-f]{8}$', fake1repo.shortid(fake1repo.getrepoid()))
    assert not fake1repo.isdirty()
    with open(os.path.join(fake1path, 'file.txt'), 'w'):
        pass
    assert not fake1repo.isdirty()
    check_call(GIT + ['add', 'file.txt'], cwd=fake1path)
    assert fake1repo.isdirty()

    clone1path = tmp_path / 'clone1'
    fake1repo.clonetopath(str(clone1path), submodules=False)
    clone1repo = path2Repo(clone1path)
    assert clone1repo.getrepoid() == fake1repo.getrepoid()

    # test repo.pullchanges() by making a change in the original fake
    assert not (clone1path / 'file.txt').exists()
    check_call(GIT + ['commit', '-m', 'Added file'], cwd=fake1path)
    clone1repo.pullchanges(submodules=False)
    assert (clone1path / 'file.txt').exists()


@pytest.mark.parametrize('with_submodules', [False, True])
def test_clonetopath(tmp_path: Path, ed2source_ro: Path, with_submodules: bool) -> None:
    """
    Ensure that clonetopath() correctly clones the source repo and uses
    --recurse-submodules to initialise submodules as well.
    """
    # ed2 is a source repo that includes submodules
    edrepo = path2Repo(ed2source_ro)
    clonepath = tmp_path / 'Desktop/ed2.git'
    edrepo.clonetopath(str(clonepath), submodules=with_submodules)

    # confirm the repo was checked out
    assert (clonepath / 'README.md').read_text() == "I am repo ed2\n"

    if with_submodules:
        # confirm first layer of submodules were initialised and checked out
        assert (clonepath / 'www/README.md').read_text() == "I am repo ed2website\n"
        assert (clonepath / 'extra/ed2models/README.md').read_text() == "I am repo ed2models\n"
        assert (clonepath / 'extra/ed2syntax/README.md').read_text() == "I am repo ed2syntax\n"

        # confirm 2nd layer of submodules were initialised and checked out
        assert (clonepath / 'extra/ed2syntax/lang/python/README.md').read_text() == "I am repo python\n"
        assert (clonepath / 'extra/ed2syntax/lang/typescript/README.md').read_text() == "I am repo typescript\n"
        assert (clonepath / 'extra/ed2syntax/lang/php/README.md').read_text() == "I am repo php\n"
        assert (clonepath / 'extra/ed2syntax/lang/html/README.md').read_text() == "I am repo html\n"

        # confirm 3rd + 4th layer of submodules were initialised and checked out
        assert (clonepath / 'extra/ed2syntax/lang/php/extensions/html/README.md').read_text() == "I am repo html\n"
        assert (clonepath / 'extra/ed2syntax/lang/php/extensions/html/extensions/css/README.md').read_text() == "I am repo css\n"

        # note that even though there's a 3rd layer for ed2syntax...html...css,
        # ed2sourcerepo is setup in a such a way that the ed2syntax...html repo
        # is committed BEFORE html...css is added as a submodule.
        assert not (clonepath / 'extra/ed2syntax/lang/html/extensions').exists()
    else:
        assert not any((clonepath / 'www').iterdir())


def test_repo_object_recognises_git_repos():
    from homely._vcs.git import Repo

    repo1 = Repo.frompath('https://github.com/johnsmith/example.git')
    assert repo1.iscanonical is True
    assert repo1.isremote is True
    assert repo1.suggestedlocal == 'example'
    assert repo1._canonical == 'https://github.com/johnsmith/example.git'

    repo2 = Repo.frompath('git@github.com:johnsmith/example.git')
    assert repo2.iscanonical is False
    assert repo2.isremote is True
    assert repo1.suggestedlocal == 'example'
    assert repo2._canonical == 'https://github.com/johnsmith/example.git'


def test_pullchanges_initialises_new_submodules(ed2source_wr: Path) -> None:
    """
    Confirm that new submodules added to the main repo or any of its children
    are initialised and checked out at the correct commit.
    """
    # Clone ed2 without submodules so they are registered but uninitialised
    clonepath = ed2sourcepath.parent / 'ed2clone'
    edrepo = path2Repo(ed2sourcepath)
    edrepo.clonetopath(str(clonepath), submodules=True)

    # 1st layer of submodules
    assert (clonepath / 'www/README.md').read_text() == "I am repo ed2website\n"
    assert (clonepath / 'extra/ed2models/README.md').read_text() == "I am repo ed2models\n"
    assert (clonepath / 'extra/ed2syntax/README.md').read_text() == "I am repo ed2syntax\n"

    # 2nd layer: language submodules inside ed2syntax
    assert (clonepath / 'extra/ed2syntax/lang/python/README.md').read_text() == "I am repo python\n"
    assert (clonepath / 'extra/ed2syntax/lang/typescript/README.md').read_text() == "I am repo typescript\n"
    assert (clonepath / 'extra/ed2syntax/lang/php/README.md').read_text() == "I am repo php\n"
    assert (clonepath / 'extra/ed2syntax/lang/html/README.md').read_text() == "I am repo html\n"

    # 3rd + 4th layer: php -> extensions/html -> extensions/css
    assert (clonepath / 'extra/ed2syntax/lang/php/extensions/html/README.md').read_text() == "I am repo html\n"
    assert (clonepath / 'extra/ed2syntax/lang/php/extensions/html/extensions/css/README.md').read_text() == "I am repo css\n"

    # ed2syntax's lang/html was registered before css was added to html,
    # so it should NOT have extensions/css
    assert not (clonepath / 'extra/ed2syntax/lang/html/extensions').exists()

    # Add some new submodules to the source repos, then propagate the updated
    # submodule pointers up through the hierarchy so the clone sees them on pull.
    tmp_path = ed2sourcepath.parent
    ed2syntax_source = tmp_path / 'ed2syntax'
    html_source = tmp_path / 'html'

    ed2docspath = makegitrepo(tmp_path, 'ed2docs')
    rustpath = makegitrepo(tmp_path, 'rust')
    jspath = makegitrepo(tmp_path, 'js')
    cpath = makegitrepo(tmp_path, 'c')

    # Add extensions/js to the standalone html source repo
    _register_submodule(html_source, 'extensions/js', jspath)

    # add extensions/c to the new Rust source repo
    _register_submodule(rustpath, 'extensions/c', cpath)

    # Update ed2syntax's lang/html pointer to include extensions/js
    check_call(['git', 'submodule', 'update', '--remote', 'lang/html'], cwd=ed2syntax_source)
    check_call(GIT + ['commit', '-m', 'update lang/html ref', 'lang/html'], cwd=ed2syntax_source)

    # Add lang/rust to the standalone ed2syntax source repo
    _register_submodule(ed2syntax_source, 'lang/rust', rustpath)

    # Add docs/ to the ed2 source repo
    _register_submodule(ed2sourcepath, 'docs', ed2docspath)

    # Update ed2's extra/ed2syntax pointer to include lang/rust + updated html
    check_call(GIT + ['submodule', 'update', '--remote', 'extra/ed2syntax'], cwd=ed2sourcepath)
    check_call(GIT + ['commit', '-m', 'Latest extra/ed2syntax', 'extra/ed2syntax'], cwd=ed2sourcepath)

    # pullchanges with submodules=True should initialise the three new submodules
    clonerepo = path2Repo(clonepath)
    clonerepo.pullchanges(submodules=True)

    # New top-level submodule: docs/
    assert (clonepath / 'docs/README.md').read_text() == "I am repo ed2docs\n"

    # New 2nd-layer submodule: lang/rust inside ed2syntax
    assert (clonepath / 'extra/ed2syntax/lang/rust/README.md').read_text() == "I am repo rust\n"

    # New submodule inside existing nested submodule: extensions/js inside html
    assert (clonepath / 'extra/ed2syntax/lang/html/extensions/js/README.md').read_text() == "I am repo js\n"

    # New 3rd-layer submodule inside new 2nd-layer submodule: lang/c inside lang/rust inside ed2syntax
    assert (clonepath / 'extra/ed2syntax/lang/rust/extensions/c/README.md').read_text() == "I am repo c\n"

    # Existing submodules should still be intact
    assert (clonepath / 'www/README.md').read_text() == "I am repo ed2website\n"
    assert (clonepath / 'extra/ed2models/README.md').read_text() == "I am repo ed2models\n"
    assert (clonepath / 'extra/ed2syntax/lang/python/README.md').read_text() == "I am repo python\n"
    assert (clonepath / 'extra/ed2syntax/lang/php/extensions/html/extensions/css/README.md').read_text() == "I am repo css\n"


@pytest.mark.parametrize('submodule_state', [
    "clean",
    "changed_files_with_conflict",
    "changed_files_no_conflict",
    "changed_subsubmodules",
    "newer_commit",
    "older_commit",
])
@pytest.mark.parametrize('parent_update_direction', [
    'forwards',
    'backwards',
])
@pytest.mark.parametrize('descendent_level', [
    'direct_submodule',
    'grandchild_submodule',
])
def test_pullchanges_updates_submodules(
    ed2sourcepath: Path,
    submodule_state: str,
    parent_update_direction: str,
    descendent_level: str,
) -> None:
    """
    Confirm that submodules (and submodule's submodules) are checked out at the
    commit specified by the parent.

    The parent might specify a newer commit or an older one for the submodule.

    BUT ONLY when the submodule is already checked out at its respective
    parent's commit *before* the parent itself is pulled/checked out

    ALSO the checkout needs to be performed in such a way that if there are
    uncommitted changes in the submodule then the changes are preserved and a
    merge conflict is NOT produced in the child repo.
    """
    tmp_path = ed2sourcepath.parent
    wwwsourcepath = tmp_path / 'ed2website'
    phpsourcepath = tmp_path / 'php'
    ed2syntaxsourcepath = tmp_path / 'ed2syntax'

    # ARRANGE PART I: add 5x new commits to a direct submodule. This gives us
    # room to move forwards or backwards later in the test.
    wwwsourcechangelog = wwwsourcepath / 'CHANGELOG.md'
    wwwcommits: dict[int, str] = {}
    for i in range(1, 6):
        wwwsourcechangelog.write_text(f'Website Version {i}\n')
        check_call(GIT + ['add', 'CHANGELOG.md'], cwd=wwwsourcepath)  # git add in case first time
        check_call(GIT + ['commit', '-m', f'Update to version {i}', 'CHANGELOG.md'], cwd=wwwsourcepath)
        wwwcommits[i] = check_output(GIT + ['rev-parse', 'HEAD'], cwd=wwwsourcepath).decode().strip()
        if i == 3:
            # update ed2source to point at this version of www
            _pull_commit_latest_submodule(ed2sourcepath, 'www', commitmsg=f'update www to v{3}')
    del wwwsourcechangelog, wwwsourcepath

    # ARRANGE PART II: Add 5x new commits to a grandchild submodule This gives us
    # room to move forwards or backwards later in the test.
    htmlsourcepath = tmp_path / 'html'
    htmlsourcechangelog = htmlsourcepath / 'CHANGELOG.md'
    htmlcommits: dict[int, str] = {}
    for i in range(1, 6):
        htmlsourcechangelog.write_text(f'HTML Version {i}\n')
        check_call(GIT + ['add', 'CHANGELOG.md'], cwd=htmlsourcepath)  # git add in case first time
        check_call(GIT + ['commit', '-m', f'Update to version {i}', 'CHANGELOG.md'], cwd=htmlsourcepath)
        htmlcommits[i] = check_output(GIT + ['rev-parse', 'HEAD'], cwd=htmlsourcepath).decode().strip()
        if i == 3:
            # update PHP syntax to point at this version of lang/HTML
            _pull_commit_latest_submodule(phpsourcepath, 'extensions/html', commitmsg=f'update extensions/html to v{3}')
    del htmlsourcepath, htmlsourcechangelog

    # the updated grandchild submodules need to have their pointers updated in
    # the parent repos all the way up the ancestory tree to the top-level ed2
    # repo.
    _pull_commit_latest_submodule(ed2syntaxsourcepath, 'lang/php')
    _pull_commit_latest_submodule(ed2sourcepath, 'extra/ed2syntax')

    # ARRANGE PART III: Clone ed2 with all submodules initialised, start messing
    # around with submodules
    clonepath = tmp_path / 'ed2clone'
    path2Repo(ed2sourcepath).clonetopath(str(clonepath), submodules=True)

    # Verify commit 3 of each submodule was checked out
    assert (clonepath / 'www/CHANGELOG.md').read_text() == "Website Version 3\n"
    assert (clonepath / 'extra/ed2syntax/lang/php/extensions/html/CHANGELOG.md').read_text() == "HTML Version 3\n"

    # advance or rewind the submodule to a different commit in the source repos
    if parent_update_direction == 'forwards':
        wwwtargetcommit = wwwcommits[5]
        htmltargetcommit = htmlcommits[5]
        commitmsg = 'Advance to commit 5'
    else:
        wwwtargetcommit = wwwcommits[1]
        htmltargetcommit = htmlcommits[1]
        commitmsg = 'Rewind to commit 1'

    # Check out the target commits in the submodules. Update intermediate submodules of the grandchild.
    _pull_commit_latest_submodule(ed2sourcepath, 'www', commitmsg=commitmsg, commitsha=wwwtargetcommit)
    _pull_commit_latest_submodule(phpsourcepath, 'extensions/html', commitmsg=commitmsg, commitsha=htmltargetcommit)
    _pull_commit_latest_submodule(ed2syntaxsourcepath, 'lang/php')
    _pull_commit_latest_submodule(ed2sourcepath, 'extra/ed2syntax')
    del commitmsg

    # what submodule we affect in the next section depends on whether we're
    # examining direct submodules or grandchild-submodules
    if descendent_level == 'direct_submodule':
        affected_submodule_path = clonepath / 'www'
        affected_submodule_commits = wwwcommits
    else:
        assert descendent_level == 'grandchild_submodule'
        affected_submodule_path = clonepath / 'extra/ed2syntax/lang/php/extensions/html'
        affected_submodule_commits = htmlcommits

    # make submodules dirty in the clone repo
    if submodule_state == "changed_files_with_conflict":
        affected_changelog = affected_submodule_path / 'CHANGELOG.md'
        affected_changelog.write_text("OOPS modified the CHANGELOG.md\n")
    elif submodule_state == "changed_files_no_conflict":
        affected_readme = affected_submodule_path / 'README.md'
        affected_readme.write_text("No dramas changing README.md\n")
    elif submodule_state == 'changed_subsubmodules':
        # change a sub-submodule of the affected submodule to a different
        # commit, so that the affected submodule's expected commit is still
        # checked out but the expected commit of the sub-submodule is not
        if descendent_level == 'direct_submodule':
            descendent_path = clonepath / 'www/assets'
        else:
            descendent_path = clonepath / 'extra/ed2syntax/lang/php/extensions/html/extensions/css'
        (descendent_path / 'README.md').write_text("This sub-submodule is modified!\n")
        check_call(GIT + ['commit', '-m', 'modify a sub-submodule', 'README.md'], cwd=descendent_path)
    elif submodule_state == 'newer_commit':
        # advance the submodule to a newer commit
        check_call(GIT + ['checkout', affected_submodule_commits[4]], cwd=affected_submodule_path)
    elif submodule_state == 'older_commit':
        # rewind the submodule to an older commit
        check_call(GIT + ['checkout', affected_submodule_commits[2]], cwd=affected_submodule_path)
    else:
        assert submodule_state == 'clean'

    # ACT: pull the latest versions of source modules - this should advance
    # both the direct submodule and the grandchild submodule if they are in a
    # "clean" state
    path2Repo(clonepath).pullchanges(submodules=True)

    # ASSERT: verify submodules are changed (or not) depending on the test paramtrs
    if parent_update_direction == 'forwards':
        expected_www_changelog = "Website Version 5\n"
        expected_html_changelog = "HTML Version 5\n"
    else:
        expected_www_changelog = "Website Version 1\n"
        expected_html_changelog = "HTML Version 1\n"

    if submodule_state == "changed_files_with_conflict":
        if descendent_level == 'direct_submodule':
            expected_www_changelog = "OOPS modified the CHANGELOG.md\n"
        else:
            expected_html_changelog = "OOPS modified the CHANGELOG.md\n"
    elif submodule_state == "changed_files_no_conflict":
        # file changes are not destroyed
        assert affected_readme.read_text() == "No dramas changing README.md\n"
    elif submodule_state == "changed_subsubmodules":
        # verify the sub-submodule wasn't moved
        assert (descendent_path / 'README.md').read_text() == "This sub-submodule is modified!\n"
    elif submodule_state == 'newer_commit':
        # if the submodules were manually moved to a newer commit, they shouldn't have been moved
        if descendent_level == 'direct_submodule':
            expected_www_changelog = "Website Version 4\n"
        else:
            expected_html_changelog = "HTML Version 4\n"
    elif submodule_state == 'older_commit':
        # if the submodules were manually moved to an older commit, they
        # shouldn't have been moved from that commit
        if descendent_level == 'direct_submodule':
            expected_www_changelog = "Website Version 2\n"
        else:
            expected_html_changelog = "HTML Version 2\n"
    else:
        assert submodule_state == 'clean'

    assert (clonepath / 'www/CHANGELOG.md').read_text() == expected_www_changelog
    assert (clonepath / 'extra/ed2syntax/lang/php/extensions/html/CHANGELOG.md').read_text() == expected_html_changelog


@pytest.mark.parametrize('submodule_state', [
    "clean",
    "changed_files",
    "changed_submodules",
    "newer_commit",
    "older_commit",
])
def test_pullchanges_removes_removed_submodules(ed2sourcepath, submodule_state):
    """
    Confirm that whenever a submodule (or submodule's submodule) is removed
    from its respective parent, the submodule folder is destroyed.

    BUT ONLY when the submodule:
    - has no uncommitted changes
    - is already checked out at the expected commit
    """


def test_pullchanges_updates_submodules_failure_aborts_nested_submodules(
    ed2sourcepath: Path,
) -> None:
    """
    Confirm that when a submodule update/checkout fails, we don't attempt to update/checkout its nested submodules either.
    """
