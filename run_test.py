#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import os
import logging
import tempfile
import pytest
import pathlib
import pkg_resources

def main():

    os.environ["pydna_data_dir"] = tempfile.mkdtemp(prefix="pydna_data_dir_")
    os.environ["pydna_log_dir"] = tempfile.mkdtemp(prefix="pydna_log_dir_")
    os.environ["pydna_config_dir"] = tempfile.mkdtemp(prefix="pydna_config_dir_")
    os.environ["pydna_loglevel"] = str(logging.DEBUG)

    installed = {pkg.key for pkg in pkg_resources.working_set}

    args = []

    if "coverage" in installed:
        print("coveralls-python is installed.")

        args = ["--cov=pydna",
                "--cov-report=html",
                "--cov-report=xml",
                "--import-mode=importlib"]
    else:
        print("coverage NOT installed! (pip install coverage)")

    if "nbval" in installed:
        print("nbval is installed.")
        args.append("--nbval")
        args.append("--current-env")
    else:
        print("nbval NOT installed! (pip install nbval)")

    mainargs = ["tests", "--capture=no", "--durations=10"] + args

    result_suite = pytest.cmdline.main(mainargs)

    from pydna import __file__ as pydnainit

    doctestdir = str(pathlib.Path(pydnainit).parent)

    doctestargs = [
        doctestdir,
        "--doctest-modules",
        "--capture=no",
        "--import-mode=importlib",
    ]
    result_doctest = pytest.cmdline.main(doctestargs)

    return result_doctest and result_suite


if __name__ == "__main__":
    result = main()
    sys.exit(result)
