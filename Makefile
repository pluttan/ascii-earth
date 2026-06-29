VENV := venv
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
