
class ConfigError(ValueError):
    """ Environments.yaml configuration error.
    """


class PrecheckError(ValueError):
    """ A precondition check failed.
    """


class MissingKey(ValueError):
    """ User is missing ssh keys in linode.
    """


class ConstraintError(ValueError):
    """ Specificed constraint is invalid.
    """


class TimeoutError(ValueError):
    """ Instance could not be provisioned before timeout.
    """


class ProviderError(Exception):
    """Instance could not be provisioned.
    """


class ProviderAPIError(Exception):
    """
    """
    def __init__(self, errors):
        self.message = errors

    def __str__(self):
        return "<ProviderAPIError message:%s>" % (str(self.message) or "Unknown")
