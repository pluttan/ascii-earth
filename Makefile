# venv lives in the user cache, NOT in the project tree. The project is served
# from the Mac over sshfs, where `python -m venv` can't create its symlinks and
# pip would crawl through ssh for every file. Caching it on the local disk fixes
# both, and stays per-project + portable (works on pcomp and on the Mac itself).
VENV := $(HOME)/.cache/ascii-earth/venv
PY   := $(VENV)/bin/python3.12
PIP  := $(VENV)/bin/pip

install:
	python3.12 -m venv $(VENV) && $(PIP) install -U pip && $(PIP) install -r requirements.txt

# Print the poster once.
run:
	$(PY) globe.py

# Spinning globe; Ctrl-C to stop.
spin:
	$(PY) globe.py --spin

# Pre-cache the Earth texture without rendering.
assets:
	$(PY) -c "from globe import fetch_texture; print(fetch_texture())"

clean:
	rm -rf $(VENV) __pycache__ *.pyc

all: install
