"""Verify built artifacts match the source repo exactly.

Passclip is a single-module package (passclip.py at wheel root), not a
package directory.  This script gates CI builds and the PyPI publish:

  * fails if dist/ contains no wheel or no sdist (a vacuous pass is a fail)
  * verifies the wheel contains exactly passclip.py + its dist-info
  * verifies the sdist contains only the expected source files
  * compares the sha256 of passclip.py inside BOTH artifacts against
    `git show HEAD:passclip.py` — a content mismatch means the build
    injected or altered code (supply-chain red flag), not just a bad layout
"""

import hashlib
import os
import subprocess
import sys
import tarfile
import zipfile

_SDIST_ALLOWED = {
    "LICENSE",
    "PKG-INFO",
    "README.md",
    "passclip.py",
    "pyproject.toml",
    "setup.cfg",
}
_SDIST_ALLOWED_DIRS = ("passclip.egg-info/", "tests/")


def _repo_passclip_sha256():
    blob = subprocess.check_output(["git", "show", "HEAD:passclip.py"])
    return hashlib.sha256(blob).hexdigest()


def _audit_wheel(path, repo_sha):
    errors = []
    name = os.path.basename(path)
    version = name.split("-")[1]
    dist_info = f"passclip-{version}.dist-info/"

    with zipfile.ZipFile(path) as z:
        files = set(z.namelist())
        if "passclip.py" not in files:
            errors.append(f"{name}: MISSING passclip.py")
        else:
            got = hashlib.sha256(z.read("passclip.py")).hexdigest()
            if got != repo_sha:
                errors.append(
                    f"{name}: passclip.py content does not match repo HEAD "
                    f"(sha256 {got[:16]}… != {repo_sha[:16]}…)"
                )
        unexpected = {f for f in files if f != "passclip.py" and not f.startswith(dist_info)}
        for uf in sorted(unexpected):
            errors.append(f"{name}: UNEXPECTED {uf}")
    return errors


def _audit_sdist(path, repo_sha):
    errors = []
    name = os.path.basename(path)
    version = name.replace("passclip-", "").replace(".tar.gz", "")
    prefix = f"passclip-{version}/"
    found_module = False

    with tarfile.open(path) as t:
        for m in t.getmembers():
            if m.name != prefix.rstrip("/") and not m.name.startswith(prefix):
                errors.append(f"{name}: member outside {prefix}: {m.name}")
                continue
            rel = m.name[len(prefix) :]
            if m.isdir() or rel == "":
                continue
            if rel == "passclip.py":
                found_module = True
                got = hashlib.sha256(t.extractfile(m).read()).hexdigest()
                if got != repo_sha:
                    errors.append(f"{name}: passclip.py content does not match repo HEAD")
            elif rel in _SDIST_ALLOWED or rel.startswith(_SDIST_ALLOWED_DIRS):
                continue
            else:
                errors.append(f"{name}: UNEXPECTED {rel}")
        if not found_module:
            errors.append(f"{name}: MISSING passclip.py")
    return errors


def audit(dist_dir="dist"):
    wheels = [f for f in os.listdir(dist_dir) if f.endswith(".whl")]
    sdists = [f for f in os.listdir(dist_dir) if f.endswith(".tar.gz")]

    errors = []
    if not wheels:
        errors.append(f"no wheel found in {dist_dir}/ — nothing was audited")
    if not sdists:
        errors.append(f"no sdist found in {dist_dir}/ — nothing was audited")

    repo_sha = _repo_passclip_sha256()
    for f in wheels:
        errors.extend(_audit_wheel(os.path.join(dist_dir, f), repo_sha))
    for f in sdists:
        errors.extend(_audit_sdist(os.path.join(dist_dir, f), repo_sha))

    if errors:
        for e in errors:
            print(f"::error::{e}", file=sys.stderr)
        sys.exit(1)
    print(
        f"Artifact audit passed: {len(wheels)} wheel(s) and {len(sdists)} "
        f"sdist(s); passclip.py content matches repo HEAD"
    )


if __name__ == "__main__":
    audit(sys.argv[1] if len(sys.argv) > 1 else "dist")
