# -*- coding: utf-8 -*-
"""Some additional batteries for time handling."""

__all__ = ["seconds_to_human", "format_human_time",
           "ETAEstimator"]

from collections import deque
import time
import typing

def seconds_to_human(s: typing.Union[float, int]) -> typing.Tuple[int, int, int, float]:
    """Convert a number of seconds into (days, hours, minutes, seconds)."""
    d = int(s // 86400)
    s -= d * 86400
    h = int(s // 3600)
    s -= h * 3600
    m = int(s // 60)
    s -= m * 60
    return d, h, m, s


def format_human_time(s: typing.Union[float, int]) -> str:
    """Convert a number of seconds to a human-readable string.

    The representation format switches automatically depending on
    how large `s` is. Examples:

        assert format_human_time(30) == "30 seconds"
        assert format_human_time(90) == "01:30"  # mm:ss
        assert format_human_time(3690) == "01:01:30"  # hh:mm:ss
        assert format_human_time(86400 + 3690) == "1 day 01:01:30"
        assert format_human_time(2 * 86400 + 3690) == "2 days 01:01:30"
    """
    d, h, m, s = seconds_to_human(s)

    if all(x == 0 for x in (d, h, m)):  # under one minute
        plural = "s" if int(s) != 1.0 else ""
        return f"{int(s):d} second{plural}"

    if d > 0:
        plural = "s" if d > 1 else ""
        days = f"{d:d} day{plural} "
    else:
        days = ""
    hours = f"{h:02d}:" if (d > 0 or h > 0) else ""
    minutes = f"{m:02d}:"
    seconds = f"{int(s):02d}"
    return f"{days}{hours}{minutes}{seconds}"


class ETAEstimator:
    """Estimate the time of completion.

    `total`: number of tasks in the whole job, used for estimating
             how much work is still needed.

             Stored in `self.total`, which is writable; but note that
             if you move the goalposts, the ETA cannot be accurate.
             Changing `self.total` is mostly useful if you suddenly
             discover that the workload is actually larger or smaller
             than what was initially expected, and want the estimate
             to reflect this sudden new information.

    `keep_last`: use the timings from at most this many most recently
                 completed tasks when computing the estimate.

                 If not given, keep all.

    If you need it, the number of tasks that have been marked completed
    is available in `self.completed`.
    """
    def __init__(self, total: int, keep_last: typing.Optional[int] = None):
        self.t1 = time.monotonic()  # time since last tick
        self.t0 = self.t1  # time since beginning
        self.total = total  # total number of work items
        self.completed = 0  # number of completed work items
        self.que = deque([], maxlen=keep_last)

    def tick(self) -> None:
        """Mark one more task as completed, automatically updating the internal timings cache."""
        self.completed += 1
        t = time.monotonic()
        dt = t - self.t1
        self.t1 = t
        self.que.append(dt)

    def _estimate(self) -> typing.Optional[float]:
        if self.completed == 0:
            return None
        # TODO: Smoother ETA?
        #
        # Let us consider the ETA estimation process as downsampling the data
        # vector (deque) into an extremely low-resolution version that has just
        # one sample.
        #
        # As we know from signal processing, as a downsampling filter, the
        # running average has an abysmal frequency response; so we should
        # expect the ETA to fluctuate wildly depending on the smoothness of
        # the input data (i.e. the time taken by each task)... which actually
        # matches observation.
        #
        # Maybe we could use a Lanczos downsampling filter to make the ETA
        # behave more smoothly?
        remaining = self.total - self.completed
        dt_avg = sum(self.que) / len(self.que)
        return remaining * dt_avg
    estimate = property(fget=_estimate, doc="Estimate of time remaining, in seconds. Computed when read; read-only. If no tasks have been marked completed yet, the estimate is `None`.")

    def _elapsed(self) -> float:
        return time.monotonic() - self.t0
    elapsed = property(fget=_elapsed, doc="Total elapsed time, in seconds. Computed when read; read-only.")

    def _formatted_eta(self) -> str:
        elapsed = self.elapsed
        estimate = self.estimate
        if estimate is not None:
            total = elapsed + estimate
            formatted_estimate = format_human_time(estimate)
            formatted_total = format_human_time(total)
        else:
            formatted_estimate = "unknown"
            formatted_total = "unknown"
        formatted_elapsed = format_human_time(elapsed)
        return f"elapsed {formatted_elapsed}, ETA {formatted_estimate}, total {formatted_total}"
    formatted_eta = property(fget=_formatted_eta, doc="Human-readable estimate, with elapsed, ETA and remaining time. See `format_human_time` for details of the format used.")
