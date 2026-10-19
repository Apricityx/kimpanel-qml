PYTHON ?= python3
RENDERER_PYTHON ?= popup-venv/bin/python
BUILD_DIR ?= build
JOBS ?= 6

.PHONY: help prepare build emoji-font renderer-env install test test-renderer test-overlay check
help:
	@echo 'prepare        Fetch pinned fcitx source and apply integration'
	@echo 'build          Build only the three user-local addons'
	@echo 'renderer-env   Create the development PySide6 environment'
	@echo 'emoji-font     Fetch the pinned private color emoji font'
	@echo 'install        Install a user-local runtime (no activation)'
	@echo 'test           Python and packaging tests (no desktop focus)'
	@echo 'test-renderer  Offscreen renderer, text motion and placement tests'
	@echo 'test-overlay   Offscreen Quickshell socket/reconnect tests'
	@echo 'check          Python tests and shell syntax'

prepare:
	$(PYTHON) scripts/build.py prepare --work-dir "$(BUILD_DIR)"
build:
	$(PYTHON) scripts/build.py build --work-dir "$(BUILD_DIR)" --jobs $(JOBS)
emoji-font:
	$(PYTHON) scripts/prepare_fonts.py
renderer-env: emoji-font
	$(PYTHON) -m venv popup-venv
	popup-venv/bin/python -m pip install -r requirements-renderer.txt
install:
	$(PYTHON) scripts/install.py --addon-dir "$(BUILD_DIR)/addons"
test:
	$(PYTHON) -m unittest discover -s tests -v
test-renderer:
	$(RENDERER_PYTHON) scripts/test_renderer.py
test-overlay:
	KIMPANEL_RENDERER_PYTHON="$(abspath $(RENDERER_PYTHON))" $(PYTHON) scripts/test_overlay.py
check: test
	@for script in kimpanel-qmlctl popup/launch packaging/fcitx5-user-local packaging/toolkit-app.sh; do bash -n "$$script" || exit; done
