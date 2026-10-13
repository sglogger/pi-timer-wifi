"""Single source of the Pi software version; keep in sync with the top entry of CHANGELOG.md."""
import os
import subprocess

VERSION = '1.3.1'


def describe():
    """Return the version plus the git commit, e.g. '1.0.0 (15fd9b6)', when run from a checkout."""
    try:
        commit = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True,
                                timeout=2, check=True, cwd=os.path.dirname(os.path.abspath(__file__)))
        return '%s (%s)' % (VERSION, commit.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        return VERSION
