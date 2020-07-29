"""
"""
import queue
from collections import deque


class GlobalGameState:
    """ Eventually handle all global game state here

    As queues are reworked they should end up here.

    This is also a good place for UI element state.
    """

    def __init__(self):
        """
        """
        self.roundtime = 0
        self.character_firstname = ""
        self.reported_time = 0  # actual time reported by the server
        self.time = 0  # time reported by the server incremented by client side clock
        self.time_last_command = 0  # the time of the last command submitted
        self.exits = dict()
        self.reset_exits()
        self.command_history = (
            queue.LifoQueue()
        )  # sometimes rt_command_queue takes back the last in

        self.lichprocess = None  # set in pylanthia.py, indirection
        self.quit_event = None  # set in pylanthia.py, not sure if that's the ideal spot
        self.input_history = list()
        self.input_history_count = 0  # must be set when used by history_scroll_mode
        self.history_scroll_mode = False  # true while scrolling history
        self.command_queue = queue.Queue()
        self.rt_command_queue = queue.Queue()

        self.urwid_scrollbar_last = 0
        self.main_view_text = ""

        # this can't be None or the slowdown on redraw gets absurdly bad
        # WINDOW_BUFFER_SIZE = 1000 # this was always fine, i think?
        # is 10000 too large? i still have slowdown when hunting...
        WINDOW_BUFFER_SIZE = 1000  # probably move to config

        # initialize with an empty string in the deque for urwid display
        # self.urwid_main_view_text = deque([''], WINDOW_BUFFER_SIZE)
        self.urwid_views = dict()
        self.urwid_views["urwid_main_view"] = deque([""], WINDOW_BUFFER_SIZE)
        self.urwid_views["urwid_chat_view"] = deque([""], WINDOW_BUFFER_SIZE)
        self.urwid_views["urwid_tcp_view"] = deque([""], WINDOW_BUFFER_SIZE)

    def reset_exits(self):
        self.exits = {
            "n": False,
            "s": False,
            "e": False,
            "w": False,
            "nw": False,
            "ne": False,
            "sw": False,
            "se": False,
        }
        return
