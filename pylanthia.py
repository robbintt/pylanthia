''' A terminal-based python client for dragonrealms

'''
import threading
import queue

import time
import itertools
import re
import datetime
import logging
import os


# this is not thread safe... need Queue.Queue
# Queue.Queue uses collections.deque and adds thread safety
from collections import deque
from itertools import islice
# lowercase in python3, fixup all deques and remove this comment
import queue

from config import *
from eaccess import get_game_key
from lib import chop_xml_and_text
from lib import get_tcp_lines
from lib import setup_game_connection
from lib import xml_parser
from lib import urwid_ui

BUF_PROCESS_SPEED = 0.01 # this is a timer for the buffer view creation thread
COMMAND_PROCESS_SPEED = 0.3 # max speed that commands are submitted at
MAX_IDLE_TIME = 60*60*2  # 60*60  # 60 minutes

# set up logging into one place for now
# see xml_parser.py for best practice importing the logger
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


def process_command_queue(global_game_state, tcp_lines):
    ''' process game commands from the submit queue

    need some hotkey to dump the queue

    don't process for n seconds if you got the response: "...wait 1 seconds."
    '''
    while True:

        # this sleep throttles max command processing speed
        time.sleep(COMMAND_PROCESS_SPEED)

        if not global_game_state.command_queue.empty():
            # maybe timestamped as its own output stream, so it can be turned off on certain windows
            submitted_command = global_game_state.command_queue.get()

            gamesock.sendall(submitted_command + b'\n')
            tcp_lines.put(b'> ' + submitted_command)
            logging.info(submitted_command)
            global_game_state.command_history.put(submitted_command)
            global_game_state.time_last_command = global_game_state.time

            if submitted_command in [b'exit', b'quit']:
                logging.info("quit triggered")
                quit_event.set()

            continue # ensure this whole queue is processed before the rt_command_queue

        # process the rt_command_queue exactly as if a player had submitted again
        # but always process the most recent player command_queue before the rt_command_queue
        # this might get caught in a little submit race with the server, how to prevent?
        # basically if there's a 1 second server time offset this could get submitted 100 times
        # this often catches itself after submitting 2 commands
        # since this puts things on the end of the queue, it gets things out of order
        # it's not really intended for long strings of commands, but still it would be unexpected
        # the user would not predict that things would start rotating like that...
        # it's complicated, the commands should have an implied order in their data structure
        # then the queue can be sorted again after putting an item on the queue
        # more info to inform the `command data structure`
        if not global_game_state.rt_command_queue.empty():
            current_roundtime = int(global_game_state.roundtime - global_game_state.time)
            if current_roundtime == 0:
                global_game_state.command_queue.put(global_game_state.rt_command_queue.get())
                

def preprocess_tcp_lines(tcp_lines, preprocessed_lines):
    ''' Process the TCP lines into labelled lines for the XML parser

    This parsing runs in its own thread
    '''
    while True:

        # only process a line if one exists
        # don't really need this check since Queue.get() is blocking by default
        # may want it to give a spinning wheel/timeout in the else
        if not tcp_lines.empty():
            preprocessed_lines.put(chop_xml_and_text.chop_xml_and_text_from_line(tcp_lines.get()))
        else:
            pass

        # this sleep throttles max line processing speed
        time.sleep(BUF_PROCESS_SPEED)


def process_lines(preprocessed_lines, player_lines):
    ''' process tcp lines back to front, works in a separate thread

    This function takes raw TCP lines and delivers annotated XML elements and text segments

    What if we use a preprocessor on the queue to create chop_xml_and_text_from_line's results
    THEN we have an XML puller thread that pulls those and processes them into XML events and another Queue
    THEN the `another queue` goes into the text filters and is displayed

    1. XML puller needs to be able to pull both XML and text lines (for multiline html text body)


    The DR output has some XML and some text.
    Sometimes a element stands alone, multiple elements per line. 
    Sometimes a element feeds into the next line.
    Sometimes XML output is multiline.
    Sometimes multiple XML structures are added on the same line.


    Goal:
    We need to be able to split a single line of multiple XML documents up.
    We also need to detect when multiple lines are one XML document.

    processing the xml-style tokens is weird
        ex. inventory streamWindow - primes inventory, but there are still more indicators...
            the final xml before the inv text is: <pushStream id='inv'/>Your worn items are:\r\n
            then after the inv text is: <popStream/>\r\n
    if i could process this multiline token, it would solve some of my issue
    a ton of tokens are duplicate and can just be dropped
    ''' 
    
    while True:
        # don't really need this check since Queue.get() is blocking by default
        # TODO: try getting rid of it sometime...
        if not preprocessed_lines.empty():
            xml_parser.process_game_xml(preprocessed_lines, text_lines, global_game_state)
        else:
            pass

        # this sleep throttles max line processing speed
        time.sleep(BUF_PROCESS_SPEED)




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

    GAME_KEY = get_game_key(eaccess_host, eaccess_port, username, password)

    # hopefully we can reuse this to reload the game if it breaks
    gamesock = setup_game_connection.setup_game_connection(server_addr, server_port, GAME_KEY, frontend_settings)

    preprocess_lines_thread = threading.Thread(target=preprocess_tcp_lines, args=(tcp_lines, preprocessed_lines))
    preprocess_lines_thread.daemon = True
    preprocess_lines_thread.start()

    process_lines_thread = threading.Thread(target=process_lines, args=(preprocessed_lines, text_lines))
    process_lines_thread.daemon = True
    process_lines_thread.start()

    tcp_thread = threading.Thread(target=get_tcp_lines.get_tcp_lines, args=(tcp_lines, gamesock))
    tcp_thread.daemon = True
    tcp_thread.start()

    command_queue_thread = threading.Thread(target=process_command_queue, args=(global_game_state, tcp_lines))
    command_queue_thread.daemon = True
    command_queue_thread.start()

    gametime_thread = threading.Thread(target=gametime_incrementer, args=(global_game_state,))
    gametime_thread.daemon = True
    gametime_thread.start()

    # start the UI and UI refresh thread
    # urwid must have its own time.sleep somewhere in its loop, since it doesn't dominate everything
    urwid_ui.urwid_main(global_game_state, player_lines, text_lines, quit_event)
