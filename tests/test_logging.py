"""Self-check des logs privés et rotatifs."""

import logging
import stat
import tempfile
from pathlib import Path

try:
    from localflow.logging_utils import configure_logging
except ModuleNotFoundError:
    configure_logging = None


def test_log_prive_et_rotatif() -> None:
    """Un LaunchAgent long-lived ne doit produire ni fichier lisible par les
    autres comptes locaux, ni log sans limite."""
    assert configure_logging is not None, "configure_logging reste à implémenter"
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "private" / "localflow.log"
        configure_logging(path, max_bytes=120, backup_count=1)
        logger = logging.getLogger("localflow")
        for index in range(30):
            logger.info("evenement technique %02d", index)
        for handler in logger.handlers:
            handler.flush()

        backup = path.with_name("localflow.log.1")
        assert path.exists()
        assert backup.exists(), "la rotation ne s'est pas déclenchée"
        assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        assert stat.S_IMODE(backup.stat().st_mode) == 0o600


def test_dossier_parent_preexistant_n_est_pas_reconfigure() -> None:
    """Un chemin personnalisé ne doit jamais changer les permissions d'un
    dossier partagé ou système qui ne nous appartient pas."""
    with tempfile.TemporaryDirectory() as tmp:
        parent = Path(tmp) / "shared"
        parent.mkdir(mode=0o755)
        path = parent / "localflow.log"
        configure_logging(path)
        logging.getLogger("localflow").info("evenement technique")
        assert stat.S_IMODE(parent.stat().st_mode) == 0o755
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_anciennes_archives_deviennent_privees() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "localflow.log"
        backup = Path(f"{path}.1")
        backup.write_text("ancien journal potentiellement sensible", encoding="utf-8")
        backup.chmod(0o644)
        configure_logging(path, backup_count=2)
        assert stat.S_IMODE(backup.stat().st_mode) == 0o600


if __name__ == "__main__":
    test_log_prive_et_rotatif()
    test_dossier_parent_preexistant_n_est_pas_reconfigure()
    test_anciennes_archives_deviennent_privees()
    print("OK : logs privés et rotatifs")
