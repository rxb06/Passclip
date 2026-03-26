"""Verify wheel contents match the source repo exactly.

Passclip is a single-module package (passclip.py at wheel root),
not a package directory.  Expected wheel layout:

    passclip.py
    passclip-<version>.dist-info/METADATA
    passclip-<version>.dist-info/WHEEL
    passclip-<version>.dist-info/RECORD
    passclip-<version>.dist-info/entry_points.txt
    passclip-<version>.dist-info/top_level.txt
    passclip-<version>.dist-info/licenses/LICENSE
"""
import os
import subprocess
import sys
import zipfile


def audit(dist_dir='dist'):
    errors = []

    for f in os.listdir(dist_dir):
        if not f.endswith('.whl'):
            continue

        with zipfile.ZipFile(os.path.join(dist_dir, f)) as z:
            wheel_files = set(z.namelist())

            # The only source file should be passclip.py
            repo_has_passclip = 'passclip.py' in set(
                subprocess.check_output(
                    ['git', 'ls-files', 'passclip.py'],
                    text=True
                ).strip().splitlines()
            )

            if not repo_has_passclip:
                errors.append("passclip.py not tracked in git")

            # Dist-info metadata (passclip-X.Y.Z.dist-info/)
            dist_info = {
                name for name in wheel_files
                if name.startswith('passclip-') and '.dist-info/' in name
            }

            # The source module
            source_files = {name for name in wheel_files if name == 'passclip.py'}

            unexpected = wheel_files - dist_info - source_files
            if unexpected:
                for uf in sorted(unexpected):
                    errors.append(f"UNEXPECTED: {uf}")

            if 'passclip.py' not in wheel_files:
                errors.append("MISSING: passclip.py not in wheel")

    if errors:
        for e in errors:
            print(f"::error::{e}", file=sys.stderr)
        sys.exit(1)
    print("Wheel audit passed")


if __name__ == '__main__':
    audit(sys.argv[1] if len(sys.argv) > 1 else 'dist')
