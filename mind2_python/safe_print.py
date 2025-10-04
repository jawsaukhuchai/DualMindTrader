import sys
import logging
from typing import Any, TextIO

logger = logging.getLogger("SafePrint")


def safe_print(
    *args: Any,
    sep: str = " ",
    end: str = "\n",
    file: TextIO = None,
    flush: bool = True,
    log_level: str = "info",
):
    """
    Safe print wrapper:
    - Always prints to stdout (capturable by pytest capsys)
    - Mirrors to logger at given log_level
    - Falls back to stderr on error
    """
    try:
        # Always write to stdout
        print(*args, sep=sep, end=end, file=sys.stdout, flush=flush)

        # Prepare message for logger
        msg = sep.join(str(a) for a in args) + ("" if end == "\n" else end)

        log_level = log_level.lower()
        if log_level == "debug":
            logger.debug(msg)
        elif log_level == "warning":
            logger.warning(msg)
        elif log_level == "error":
            logger.error(msg)
        else:
            logger.info(msg)

    except Exception as e:
        # fallback to stderr
        try:
            sys.stderr.write(f"[safe_print error] {e}\n")
            sys.stderr.flush()
        except Exception:
            pass
