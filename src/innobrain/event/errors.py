class EventPackageError(RuntimeError):
    """Base error for event-package build, verification and runtime operations."""


class EventSchemaError(EventPackageError):
    pass


class EventIntegrityError(EventPackageError):
    pass


class EventSignatureError(EventPackageError):
    pass


class EventCompatibilityError(EventPackageError):
    pass


class EventInstallError(EventPackageError):
    pass


class EventActivationError(EventPackageError):
    pass


class EventActivationBusy(EventActivationError):
    pass
