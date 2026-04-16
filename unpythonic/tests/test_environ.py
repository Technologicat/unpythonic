# -*- coding: utf-8 -*-

from ..syntax import macros, test, test_raises, the  # noqa: F401
from ..test.fixtures import session, testset

import os

from ..environ import override

def runtests():
    with testset("environ.override"):
        # Basic override and restore
        os.environ["_UNPYTHONIC_TEST_VAR"] = "original"
        with override(_UNPYTHONIC_TEST_VAR="overridden"):
            test[the[os.environ["_UNPYTHONIC_TEST_VAR"]] == "overridden"]
        test[the[os.environ["_UNPYTHONIC_TEST_VAR"]] == "original"]
        del os.environ["_UNPYTHONIC_TEST_VAR"]

        # Adding a variable that didn't exist before
        key = "_UNPYTHONIC_TEST_NEW"
        if key in os.environ:
            del os.environ[key]
        with override(**{key: "added"}):
            test[the[os.environ[key]] == "added"]
        test[key not in os.environ]

        # Multiple overrides at once
        os.environ["_UNPYTHONIC_TEST_A"] = "a_orig"
        os.environ["_UNPYTHONIC_TEST_B"] = "b_orig"
        with override(_UNPYTHONIC_TEST_A="a_new", _UNPYTHONIC_TEST_B="b_new"):
            test[the[os.environ["_UNPYTHONIC_TEST_A"]] == "a_new"]
            test[the[os.environ["_UNPYTHONIC_TEST_B"]] == "b_new"]
        test[the[os.environ["_UNPYTHONIC_TEST_A"]] == "a_orig"]
        test[the[os.environ["_UNPYTHONIC_TEST_B"]] == "b_orig"]
        del os.environ["_UNPYTHONIC_TEST_A"]
        del os.environ["_UNPYTHONIC_TEST_B"]

        # Nested overrides (same-thread; RLock allows this)
        os.environ["_UNPYTHONIC_TEST_VAR"] = "level0"
        with override(_UNPYTHONIC_TEST_VAR="level1"):
            test[the[os.environ["_UNPYTHONIC_TEST_VAR"]] == "level1"]
            with override(_UNPYTHONIC_TEST_VAR="level2"):
                test[the[os.environ["_UNPYTHONIC_TEST_VAR"]] == "level2"]
            test[the[os.environ["_UNPYTHONIC_TEST_VAR"]] == "level1"]
        test[the[os.environ["_UNPYTHONIC_TEST_VAR"]] == "level0"]
        del os.environ["_UNPYTHONIC_TEST_VAR"]

        # Restore on exception
        os.environ["_UNPYTHONIC_TEST_VAR"] = "before"
        try:
            with override(_UNPYTHONIC_TEST_VAR="during"):
                test[the[os.environ["_UNPYTHONIC_TEST_VAR"]] == "during"]
                raise RuntimeError("boom")
        except RuntimeError:
            pass
        test[the[os.environ["_UNPYTHONIC_TEST_VAR"]] == "before"]
        del os.environ["_UNPYTHONIC_TEST_VAR"]

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
