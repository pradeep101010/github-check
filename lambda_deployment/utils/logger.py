import logging
import sys


class Logger:
    _logger = None

    @staticmethod
    def get_logger(name: str = "app", level=logging.INFO):
        """
        Returns a centralized logger instance.
        """
        if Logger._logger:
            return Logger._logger

        logger = logging.getLogger(name)
        logger.setLevel(level)

        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
        )

        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)

        logger.addHandler(handler)
        logger.propagate = False

        Logger._logger = logger
        return logger
    