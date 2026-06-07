import sys
import logging
from loguru import logger
from logtail import LogtailHandler


def _logtail_sink(handler: LogtailHandler):
    def sink(message):
        record = message.record
        log_record = logging.LogRecord(
            name=record["name"],
            level=record["level"].no,
            pathname=record["file"].path,
            lineno=record["line"],
            msg=record["message"],
            args=(),
            exc_info=record["exception"],
        )
        handler.emit(log_record)
    return sink


def setup_logging(logtail_token: str | None = None, log_level: str = "INFO"):
    logger.remove()

    # Terminal
    logger.add(
        sys.stdout,
        level="DEBUG",
        colorize=True,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{line}</cyan> — "
            "<level>{message}</level>"
        ),
    )

    # Better Stack
    if logtail_token:
        logtail_handler = LogtailHandler(source_token=logtail_token)
        logtail_handler.setLevel(log_level)
        logger.add(_logtail_sink(logtail_handler), level=log_level, format="{message}")
        logger.info("Better Stack activé")