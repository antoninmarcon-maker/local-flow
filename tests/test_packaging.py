"""Self-check du contenu réellement distribué dans wheel et sdist."""

import subprocess
import tarfile
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_distribution_minimale_et_shim_embarque() -> None:
    """Le wheel doit faire fonctionner Apple Intelligence après installation,
    tandis que le sdist ne doit pas publier tests et notes de chantier."""
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp)
        subprocess.run(
            ["uv", "build", "--offline", "--no-create-gitignore", "--out-dir", str(output)],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        wheel = next(output.glob("*.whl"))
        sdist = next(output.glob("*.tar.gz"))
        with zipfile.ZipFile(wheel) as archive:
            wheel_names = archive.namelist()
        with tarfile.open(sdist) as archive:
            sdist_names = archive.getnames()

        assert "localflow/data/afmshim.swift" in wheel_names
        assert not any("/tasks/" in name for name in sdist_names)
        assert not any("/tests/" in name for name in sdist_names)
        assert not any("/docs/" in name for name in sdist_names)


if __name__ == "__main__":
    test_distribution_minimale_et_shim_embarque()
    print("OK : distribution minimale et shim embarqué")
