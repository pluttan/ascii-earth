# venv lives in the user cache, NOT in the project tree. The project is served
# from the Mac over sshfs, where `python -m venv` can't create its symlinks and
# pip would crawl through ssh for every file. Caching it on the local disk fixes
# both, and stays per-project + portable (works on pcomp and on the Mac itself).
VENV := $(HOME)/.cache/ascii-earth/venv
PY   := $(VENV)/bin/python3.12
PIP  := $(VENV)/bin/pip

install:
	python3.12 -m venv $(VENV) && $(PIP) install -U pip && $(PIP) install -r requirements.txt

# Interactive globe: hjkl/arrows spin, +/- zoom, space auto, q quit.
run:
	$(PY) globe.py -i

# Print the poster once (no interaction).
poster:
	$(PY) globe.py

# Auto-spinning globe; Ctrl-C to stop.
spin:
	$(PY) globe.py --spin

# Pre-cache every body's texture without rendering.
assets:
	$(PY) -c "import globe; [globe.body_texture(b) for b in globe.BODY_NAMES]; print('cached', len(globe.BODY_NAMES), 'bodies')"

clean:
	rm -rf $(VENV) __pycache__ *.pyc

all: install
