class JsonError(Exception):
    pass


class HelperError(Exception):
    """
    Raised when one of the helpers experiences a problem.
    """


class RepoError(Exception):
    """
    Raised when something tries to use a git (or other VCS) repo and there is a
    problem accessing the repo.
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
