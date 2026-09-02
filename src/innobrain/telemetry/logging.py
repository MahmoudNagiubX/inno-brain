import logging

_HANDLER_MARKER = "_innobrain_handler"


def configure_logging(
    logger: logging.Logger | None = None,
    level: int = logging.INFO,
) -> logging.Logger:
    configured_logger = logger or logging.getLogger("innobrain")
    configured_logger.setLevel(level)
    configured_logger.propagate = False

    for handler in configured_logger.handlers:
        if getattr(handler, _HANDLER_MARKER, False):
            handler.setLevel(level)
            return configured_logger

    handler = logging.StreamHandler()
    setattr(handler, _HANDLER_MARKER, True)
    handler.setLevel(level)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    configured_logger.addHandler(handler)
    return configured_logger
