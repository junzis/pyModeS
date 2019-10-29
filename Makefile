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
	find . | grep -E "(__pycache__|\.pyc|\.pyo$$)" | xargs rm -rf
	rm -rf *.egg-info
	rm -rf .pytest_cache
	rm -rf build/*
