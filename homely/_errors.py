# Various error messages that we should to the user. These are in constants so
# we can import them in the system tests and ensure that they appear in the
# output.
ERR_NOT_A_REPO = "Not a git repository"
ERR_NO_COMMITS = "Repository doesn't have any commits"
ERR_NO_SCRIPT = "Repository doesn't have a HOMELY.py script"


class JsonError(Exception):
    pass


class InputError(Exception):
    """
    Raised when the user can't or doesn't provide a valid answer to a yesno()
    question.
    """


class HelperError(Exception):
    """
    Raised when one of the helpers experiences a problem.
    """


class RepoError(Exception):
    """
    Raised when something tries to use a git (or other VCS) repo and there is a
    problem accessing the repo.
    """


class NotARepo(RepoError):
    """
    Raised when a path isn't a real repo
    """
    def __init__(self, repo_path):
        super(NotARepo, self).__init__()
        self.repo_path = repo_path


class RepoHasNoCommitsError(RepoError):
    """
    Raised when you try to get the ID of a repo, but it has no commits.
    """


class SystemError(Exception):
    """
    Raised by the homely._utils.run() function when a subprocess does not
    return an expected error code.
    """


class ConnectionError(Exception):
    """
    Raised when a remote resource just as git repo or download URL are not
    reachable
    """


# TODO: merge this with CleanupObstruction ... I don't think its worthwhile
# having them as separate
class CleanupConflict(Exception):
    def __init__(self, *args, **kwargs):
        import pprint
        print('args = ' + pprint.pformat(args))  # noqa TODO
        import pprint
        print('kwargs = ' + pprint.pformat(kwargs))  # noqa TODO
        # which is the path that needs cleaning up?
        self.conflictpath = kwargs.pop('conflictpath')
        # who still wants this path to hang around?
        self.pathwanter = kwargs.pop('pathwanter')
        super(CleanupConflict, self).__init__(*args, **kwargs)


# TODO: work out if this is still needed?
class CleanupObstruction(Exception):
    def __init__(self, *args, **kwargs):
        # which cleaner
        self.cleaner = kwargs.pop('cleaner')
        # what was the reason given?
        self.why = kwargs.pop('why')
        super(CleanupObstruction, self).__init__(*args, **kwargs)
