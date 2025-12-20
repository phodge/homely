# HOMELY

https://homely.readthedocs.io/


## Developing

Homely's `pyproject.toml` is managed using uv.

To create a virtualenv for development:

    uv venv [ -p some_python ] --seed path/to/virtualenv
    source path/to/virtualenv/bin/activate
    pip install --upgrade pip  # this may be required on older versions of python like 3.10
    pip install -e . --group dev

To quickly run tests:

    source path/to/virtualenv/bin/activate
    pytest test/test_some_feature.py

    # NOTE: the virtualenv must be manually activated because of the way that some tests use
    # subprocesses.
