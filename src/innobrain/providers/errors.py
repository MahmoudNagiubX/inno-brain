class ProviderError(RuntimeError):
    """Base error for an unavailable or failed external provider."""


class MissingProviderCredential(ProviderError):
    """The provider cannot be used because a required credential is absent."""


class ProviderUnavailable(ProviderError):
    """The provider is configured but cannot currently serve a request."""


class ProviderTimeout(ProviderError):
    """The provider did not respond within the adapter's timeout."""
