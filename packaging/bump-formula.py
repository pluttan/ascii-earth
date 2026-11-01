"""Point the Homebrew formula at a released version of ascii-earth.

Takes SHA256SUMS of the GitHub release, writes the version, the four archive
addresses and their sums into Formula/ascii-earth.rb of the tap checkout next to
this repository (../homebrew-tap), then commits and pushes the tap.

Run after the release workflow has finished:  make formula V=1.2.1

Signed: pluttan
"""

import re
import subprocess
import sys
import urllib.request
from pathlib import Path

REPO = "pluttan/ascii-earth"
TAP = Path(__file__).resolve().parents[2] / "homebrew-tap"
FORMULA = TAP / "Formula" / "ascii-earth.rb"
TARGETS = ("darwin-arm64", "darwin-x86_64", "linux-arm64", "linux-x86_64")


def sums(version: str) -> dict:
    url = f"https://github.com/{REPO}/releases/download/v{version}/SHA256SUMS"
    with urllib.request.urlopen(url, timeout=60) as r:
        text = r.read().decode()
    found = {}
    for line in text.splitlines():
        digest, name = line.split()
        found[name.removeprefix("ascii-earth-").removesuffix(".tar.gz")] = digest
    missing = [t for t in TARGETS if t not in found]
    if missing:
        sys.exit(f"no archive for {', '.join(missing)} in v{version}")
    return found


def main():
    if len(sys.argv) != 2 or not re.fullmatch(r"\d+\.\d+\.\d+", sys.argv[1]):
        sys.exit("usage: bump-formula.py 1.2.1")
    version = sys.argv[1]
    digests = sums(version)
    text = FORMULA.read_text()
    text = re.sub(r'version "[^"]+"', f'version "{version}"', text)
    for target in TARGETS:
        # Each url line is followed by the sha256 line of the same archive.
        text, n = re.subn(
            rf'url "https://github.com/{REPO}/releases/download/v[^/]+/ascii-earth-{target}\.tar\.gz"\n(\s+)sha256 "[0-9a-f]+"',
            f'url "https://github.com/{REPO}/releases/download/v{version}/ascii-earth-{target}.tar.gz"\n'
            rf'\g<1>sha256 "{digests[target]}"',
            text)
        if n != 1:
            sys.exit(f"formula has no single url for {target}")
    FORMULA.write_text(text)
    git = ["git", "-C", str(TAP)]
    subprocess.run(git + ["add", str(FORMULA)], check=True)
    subprocess.run(git + ["commit", "-q", "-m", f"ascii-earth {version}"], check=True)
    subprocess.run(git + ["push", "-q", "origin", "HEAD"], check=True)
    print(f"formula: ascii-earth {version}, pushed")


if __name__ == "__main__":
    main()
