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
