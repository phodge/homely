import pytest
from pathlib import Path

from homely._test import contents
from homely._test.system import HOMELY, TempRepo, getsystemfn


@pytest.mark.parametrize("use_venv", [False, True])
def test_add_repo_with_virtualenv_config_gets_a_virtualenv(tmpdir, HOME, use_venv):
    system = getsystemfn(HOME)

    statefile = Path(tmpdir) / 'statefile.txt'
    desired_venv_path = Path(HOME) / 'dotfiles-venv'

    # make a fake repo that wants its own virtualenv with one of our dummy packages
    repo1 = TempRepo(tmpdir, 'repo1')
    contents(repo1.remotepath + '/HOMELY.py',
             f"""
             import os

             with open("{statefile}", 'w') as f:
                f.write(os.getenv("VIRTUAL_ENV", "no virtualenv"))
             """)

    if use_venv:
        # add pyproject.toml that requests a virtualenv
        contents(repo1.remotepath + '/pyproject.toml',
                 f"""
                 [tool.homely.virtualenv]
                 use_virtualenv = true
                 virtualenv_path = "{desired_venv_path}"
                 """)

    system(HOMELY('add') + [repo1.url])

    if use_venv:
        assert Path(statefile).read_text() == str(desired_venv_path)
    else:
        assert Path(statefile).read_text() == "no virtualenv"


def ztest_update_repo_reuses_existing_virtualenv():
    raise Exception("TODO: wot")  # noqa


def ztest_update_repo_discovers_new_virtualenv_config():
    raise Exception("TODO: wot")  # noqa


def ztest_repo_virtualenv_is_updated_when_repo_contents_change():
    raise Exception("TODO: wheeee")  # noqa


def ztest_update_repo_doesnt_use_virtualenv_if_config_disappears():
    raise Exception("TODO: wot")  # noqa


def ztest_repo_virtualenv_cleaned_up_when_repo_removed():
    raise Exception("TODO: wot")  # noqa


def ztest_repo_virtualenv_cleaned_up_when_repo_no_longer_wants_one():
    raise Exception("TODO: wot")  # noqa


def ztest_repo_virtualenv_cleaned_up_when_repo_asks_for_a_new_path():
    raise Exception("TODO: wot")  # noqa
