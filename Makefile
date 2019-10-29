install:
	pip install . --upgrade

uninstall:
	pip uninstall pyModeS -y

ext:
	python setup.py build_ext --inplace

test:
	python -m pytest

clean:
	find pyModeS/c_decoder -type f -name '*.c' -delete
	find pyModeS/c_decoder -type f -name '*.so' -delete
	find . -name "__pycache__" -type d -exec rm -r "{}" \;
	rm -rf *.egg-info
	rm -rf build/*
