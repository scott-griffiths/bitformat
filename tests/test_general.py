#!/usr/bin/env python

import bitformat
import tomllib

def test_version_number():
    with open("../pyproject.toml") as f:
        pyproject_data = tomllib.loads(f.read())
        toml_version = pyproject_data["project"]["version"]
        assert bitformat.__version__ == toml_version