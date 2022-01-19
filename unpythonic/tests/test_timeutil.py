# -*- coding: utf-8 -*-

from ..syntax import macros, test  # noqa: F401
from ..test.fixtures import session, testset, returns_normally

from ..timeutil import seconds_to_human, format_human_time, ETAEstimator

def runtests():
    with testset("seconds_to_human"):
        test[seconds_to_human(30) == (0, 0, 0, 30)]
        test[seconds_to_human(30.0) == (0, 0, 0, 30.0)]
        test[seconds_to_human(90) == (0, 0, 1, 30)]
        test[seconds_to_human(3690) == (0, 1, 1, 30)]
        test[seconds_to_human(86400 + 3690) == (1, 1, 1, 30)]
        test[seconds_to_human(2 * 86400 + 3690) == (2, 1, 1, 30)]

    with testset("format_human_time"):
        test[format_human_time(30) == "30 seconds"]
        test[format_human_time(90) == "01:30"]  # mm:ss
        test[format_human_time(3690) == "01:01:30"]  # hh:mm:ss
        test[format_human_time(86400 + 3690) == "1 day 01:01:30"]
        test[format_human_time(2 * 86400 + 3690) == "2 days 01:01:30"]

    # This is a UI thing so we can't test functionality reliably. Let's just check it doesn't crash.
    with testset("ETAEstimator"):
        e = ETAEstimator(total=5)
        test[returns_normally(e.estimate)]  # before the first tick
        test[returns_normally(e.elapsed)]
        test[returns_normally(e.formatted_eta)]
        test[returns_normally(e.tick())]
        test[returns_normally(e.estimate)]  # after the first tick
        test[returns_normally(e.elapsed)]
        test[returns_normally(e.formatted_eta)]

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
