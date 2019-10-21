''' A terminal-based python client for dragonrealms

'''
import threading
import time
import datetime
import logging
import os

# this is not thread safe... need Queue.Queue
# Queue.Queue uses collections.deque and adds thread safety
from collections import deque
# lowercase in python3, fixup all deques and remove this comment
import queue

# used for setup_game_connection, eaccess
from config import eaccess_host, eaccess_port, username, password, character, gamestring, server_addr, server_port, frontend_settings

from lib import eaccess
from lib import setup_game_connection
from lib import get_tcp_lines
from lib import text_processing
from lib import command_processing
from lib import urwid_ui

MAX_IDLE_TIME = 60*60*2  # 60*60  # 60 minutes

# set up logging into one place for now
# see lib/xml_parser.py for best practice importing the logger
# from: https://stackoverflow.com/a/15735146
log_filename = "{}_log.{}.txt".format('dr', datetime.datetime.now().strftime('%Y-%m-%d.%H:%M:%S'))
log_directory = "logs"
log_location = os.path.join(log_directory, log_filename)
logging.basicConfig(filename=log_location, level=logging.INFO)

class GlobalGameState:
    '''
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


def gametime_incrementer(global_game_state):
    '''
    '''
    while True:
        time.sleep(1)

        # this is incremented since we only get gametime about every 5-20 seconds
        global_game_state.time += 1

        # this should only run the first time global game state is set
        # otherwise (as it is now) we check this way more than necessary...
        # funky hack to make sure we aren't incrementing from zero still
        # it's acceptable to use a known global game time since it increments forever but still sloppy
        if global_game_state.time > 100000 and global_game_state.time_last_command == 0:
            global_game_state.time_last_command = global_game_state.time

        # quit if idle too long
        time_since_last_command = global_game_state.time - global_game_state.time_last_command 
        if time_since_last_command >= MAX_IDLE_TIME:
            global_game_state.command_queue.put(b'quit')


if __name__ == '__main__':
    ''' Set up the connection and start the threads

    note: preprocess_lines_thread.daemon = True # closes when main thread ends
    '''
    global_game_state = GlobalGameState()

    tcp_lines = queue.Queue() # split the tcp buffer on '\r\n'
    preprocessed_lines = queue.Queue()
    text_lines = queue.Queue()
    player_lines = deque() # process the xml into a player log, which can also be a player view

    quit_event = threading.Event() # set this flag with quit_event.set() to quit from main thread

    GAME_KEY = eaccess.get_game_key(eaccess_host, eaccess_port, username, password, character, gamestring)

    # hopefully we can reuse this to reload the game if it breaks
    gamesock = setup_game_connection.setup_game_connection(server_addr, server_port, GAME_KEY, frontend_settings)

    preprocess_lines_thread = threading.Thread(target=text_processing.preprocess_tcp_lines, args=(tcp_lines, preprocessed_lines))
    preprocess_lines_thread.daemon = True
    preprocess_lines_thread.start()

    process_lines_thread = threading.Thread(target=text_processing.process_lines, args=(preprocessed_lines, text_lines, global_game_state))
    process_lines_thread.daemon = True
    process_lines_thread.start()

    tcp_thread = threading.Thread(target=get_tcp_lines.get_tcp_lines, args=(tcp_lines, gamesock))
    tcp_thread.daemon = True
    tcp_thread.start()

    command_queue_thread = threading.Thread(target=command_processing.process_command_queue, args=(global_game_state, tcp_lines, gamesock))
    command_queue_thread.daemon = True
    command_queue_thread.start()

    gametime_thread = threading.Thread(target=gametime_incrementer, args=(global_game_state,))
    gametime_thread.daemon = True
    gametime_thread.start()

    # start the UI and UI refresh thread
    # urwid must have its own time.sleep somewhere in its loop, since it doesn't dominate everything
    urwid_ui.urwid_main(global_game_state, player_lines, text_lines, quit_event)
