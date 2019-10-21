'''
'''
import queue

class GlobalGameState:
    ''' Eventually handle all global game state here

    As queues are reworked they should end up here.

    This is also a good place for UI element state.
    '''
    def __init__(self):
        '''
        '''
        self.roundtime = 0
        self.reported_time = 0 # actual time reported by the server
        self.time = 0 # time reported by the server incremented by client side clock
        self.time_last_command = 0 # the time of the last command submitted
        self.exits = dict()
        self.reset_exits()
        self.command_history = queue.LifoQueue() # sometimes rt_command_queue takes back the last in
        self.input_history = list()
        self.input_history_count = 0 # must be set when used by history_scroll_mode
        self.history_scroll_mode = False  # true while scrolling history
        self.command_queue = queue.Queue()
        self.rt_command_queue = queue.Queue()


    def reset_exits(self):
        self.exits = { 'n': False,
                       's': False,
                       'e': False,
                       'w': False,
                       'nw': False,
                       'ne': False,
                       'sw': False,
                       'se': False }
        return
