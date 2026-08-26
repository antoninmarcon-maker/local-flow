"""Journal technique local, privé et borné pour le LaunchAgent."""

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

DEFAULT_MAX_BYTES = 1_000_000
DEFAULT_BACKUP_COUNT = 2


class _SecureRotatingFileHandler(RotatingFileHandler):
    """RotatingFileHandler dont chaque nouveau fichier est créé en 0600."""

    def _open(self):
        path = Path(self.baseFilename)
        # Le chemin peut venir de l'environnement. Ne jamais chmod un dossier
        # préexistant arbitraire (par exemple /tmp ou ~/Library/Logs) : seul un
        # dossier créé par LocalFlow nous appartient.
        parent_existed = path.parent.exists()
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not parent_existed:
            path.parent.chmod(0o700)
        flags = os.O_WRONLY | os.O_CREAT
        flags |= os.O_APPEND if "a" in self.mode else os.O_TRUNC
        fd = os.open(path, flags, 0o600)
        os.chmod(path, 0o600)
        return os.fdopen(fd, self.mode, encoding=self.encoding, errors=self.errors)


def configure_logging(
    log_file: str | Path | None = None,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
    backup_count: int = DEFAULT_BACKUP_COUNT,
) -> logging.Logger:
    """Configure le logger LocalFlow pour le terminal ou un fichier rotatif."""
    logger = logging.getLogger("localflow")
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()

    if log_file:
        handler: logging.Handler = _SecureRotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        log_path = Path(log_file)
        for index in range(backup_count + 1):
            candidate = log_path if index == 0 else Path(f"{log_path}.{index}")
            if candidate.is_file() and not candidate.is_symlink():
                candidate.chmod(0o600)
    else:
        handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger
