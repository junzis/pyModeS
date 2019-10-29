ext:
	python setup.py build_ext --inplace

test:
	python -m pytest

clean:
	python setup.py clean --all
	find pyModeS/c_decoder -type f -name '*.c' -delete
	find pyModeS/c_decoder -type f -name '*.so' -delete
