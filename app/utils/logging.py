import logging
from logging.handlers import RotatingFileHandler
import os
from typing import Optional


def setup_logger(name: str = 'mailsage', log_file: Optional[str] = None,
                 level: int = logging.INFO) -> logging.Logger:
    """Setup and configure logger."""

    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Create formatters and add it to handlers
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Create stream handler (console output)
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(level)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    # If log file is specified, create file handler
    if log_file:
        # Ensure log directory exists
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)

        # Create rotating file handler
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10000000,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


# Create default logger instance
logger = setup_logger(
    log_file='logs/mailsage.log' if os.environ.get('FLASK_ENV'
                                                   ) != 'testing' else None
)

# Usage example:
# logger.info("Operation successful")
# logger.error("An error occurred", exc_info=True)
# logger.warning("Warning message")
# logger.debug("Debug information")
