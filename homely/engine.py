def run_update(localpath):
    heading("Updating %s" % localpath)
    if pull_first:
        # FIXME: warn if there are oustanding changes in the repo
        # FIXME: allow the user to configure whether they want to use 'git pull' or some other
        # command to update the repo
        echo("%s: Retrieving updates using git pull" % localpath)
        cmd = ['git', '-C', path, 'pull']
        subprocess.check_call(cmd)
    else:
        # FIXME: notify the user if there are oustanding changes in the repo
        pass
    raise Exception("TODO: run the repo's homely.py script")  # noqa


def clone_online_repo(repo_path):
    assert len(repo_path)
    raise Exception("TODO: git clone the repo")  # noqa
    raise Exception("TODO: return the path to the local copy of the repo")  # noqa
    # FIXME: check to see if the repo already exists locally
    # FIXME: suggest a good default location for the local clone of the repo
    return local_path
