# -*- coding: utf-8; -*-
"""ANSI color support for *nix terminals.

For a serious library that does this sort of thing in a cross-platform way,
see Colorama:
    https://github.com/tartley/colorama
"""

# TODO: We could also use Colorama (which also works on Windows), but that's one more dependency.
# TODO: Maybe this module should live in unpythonic.net, though we don't currently use it there.

from enum import Enum

__all__ = ["TC", "colorize"]

class TC(Enum):
    """Terminal colors, via ANSI escape sequences.

    This uses the terminal app palette (16 colors), so e.g. LIGHTGREEN may actually
    be blue, depending on the user's color scheme.

    The colors are listed in palette order.

    See:
        https://en.wikipedia.org/wiki/ANSI_escape_code#SGR_(Select_Graphic_Rendition)_parameters
        https://stackoverflow.com/questions/287871/print-in-terminal-with-colors
        https://github.com/tartley/colorama
    """
    # For grepping: \33 octal is \x1b hex.
    RESET = '\33[0m'  # return to normal state, ending colorization
    RESETSTYLE = '\33[22m'  # return to normal brightness
    RESETFG = '\33[39m'
    RESETBG = '\33[49m'

    # styles
    BRIGHT = '\33[1m'  # a.k.a. bold
    DIM = '\33[2m'
    ITALIC = '\33[3m'
    URL = '\33[4m'  # underline plus possibly a special color (depends on terminal app)
    BLINK = '\33[5m'
    BLINK2 = '\33[6m'  # same effect as BLINK?
    SELECTED = '\33[7m'

    # foreground colors
    BLACK = '\33[30m'
    RED = '\33[31m'
    GREEN = '\33[32m'
    YELLOW = '\33[33m'
    BLUE = '\33[34m'
    MAGENTA = '\33[35m'
    CYAN = '\33[36m'
    WHITE = '\33[37m'
    LIGHTBLACK = '\33[90m'
    LIGHTRED = '\33[91m'
    LIGHTGREEN = '\33[92m'
    LIGHTYELLOW = '\33[93m'
    LIGHTBLUE = '\33[94m'
    LIGHTMAGENTA = '\33[95m'
    LIGHTCYAN = '\33[96m'
    LIGHTWHITE = '\33[97m'

    # background colors
    BLACKBG = '\33[40m'
    REDBG = '\33[41m'
    GREENBG = '\33[42m'
    YELLOWBG = '\33[43m'
    BLUEBG = '\33[44m'
    MAGENTABG = '\33[45m'
    CYANBG = '\33[46m'
    WHITEBG = '\33[47m'

def colorize(s, *colors):
    """Colorize string `s` for ANSI terminal display. Reset color at end of `s`.

    For available `colors`, see the `TC` enum.

    Usage::

        colorize("I'm new here", TC.GREEN)
        colorize("I'm bold and bluetiful", TC.BRIGHT, TC.BLUE)

    Each entry can also be a `tuple` (arbitrarily nested), which is useful
    for defining compound styles::

        BRIGHT_BLUE = (TC.BRIGHT, TC.BLUE)
        ...
        colorize("I'm bold and bluetiful, too", BRIGHT_BLUE)
    """
    def get_ansi_color_sequence(c):  # recursive, so each entry can be a tuple.
        if isinstance(c, tuple):
            return "".join(get_ansi_color_sequence(elt) for elt in c)
        if not isinstance(c, TC):
            raise TypeError("Expected a TC instance, got {} with value '{}'".format(type(c), c))  # pragma: no cover
        return c.value
    return "{}{}{}".format(get_ansi_color_sequence(colors),
                           s,
                           get_ansi_color_sequence(TC.RESET))
