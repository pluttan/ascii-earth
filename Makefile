# venv lives in the user cache, NOT in the project tree. The project is served
# from the Mac over sshfs, where `python -m venv` can't create its symlinks and
# pip would crawl through ssh for every file. Caching it on the local disk fixes
# both, and stays per-project + portable (works on pcomp and on the Mac itself).
VENV := $(HOME)/.cache/ascii-earth/venv
PY   := $(VENV)/bin/python3.12
PIP  := $(VENV)/bin/pip

install:
	python3.12 -m venv $(VENV) && $(PIP) install -U pip && $(PIP) install -r requirements.txt

# Interactive globe: drag/arrows rotate, wheel/+- zoom, ? for all keys, q quit.
run:
	$(PY) -m ascii_earth -i

# Print the poster once (no interaction).
poster:
	$(PY) -m ascii_earth

# Auto-spinning globe; Ctrl-C to stop.
spin:
	$(PY) -m ascii_earth --spin

clean:
	rm -rf $(VENV) ascii_earth/__pycache__ *.pyc

all: install

# Pictures of the Habr article: docs/article/img (fonts in docs/fonts).
figures:
	$(VENV)/bin/pip install -q matplotlib && $(PY) docs/article/figures.py

# One-folder build with Python and the maps inside: dist/ascii-earth/ascii-earth.
# The release workflow runs it on each OS; install.sh and Homebrew take the result.
.PHONY: dist figures
dist:
	$(PY) -m PyInstaller --onedir --name ascii-earth --paths $(CURDIR) \
		--add-data "$(CURDIR)/ascii_earth/textures:ascii_earth/textures" \
		--exclude-module matplotlib --exclude-module tkinter --exclude-module PyInstaller \
		--specpath build --noconfirm --log-level WARN packaging/entry.py
