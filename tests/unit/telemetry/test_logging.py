import logging

from innobrain.telemetry import configure_logging


def test_configure_logging_is_idempotent() -> None:
    logger = logging.getLogger("innobrain.test.idempotent")
    original_handlers = list(logger.handlers)
    try:
        for handler in original_handlers:
            logger.removeHandler(handler)

        configure_logging(logger)
        configure_logging(logger)

        innobrain_handlers = [
            handler
            for handler in logger.handlers
            if getattr(handler, "_innobrain_handler", False)
        ]
        assert len(innobrain_handlers) == 1
        assert logger.propagate is False
    finally:
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
        for handler in original_handlers:
            logger.addHandler(handler)
