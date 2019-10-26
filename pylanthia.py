''' A terminal-based python client for dragonrealms

'''
import threading
import queue

import os
import logging
import datetime

# used temporarily in player_lines for urwid_ui view, NOT thread-safe
from collections import deque 

from lib import setup_game_connection
from lib import game_state
from lib import gametime_incrementor
from lib import get_tcp_lines
from lib import text_processing
from lib import command_processing
from lib import urwid_ui

# TODO: move logging to a lib module
# see lib/xml_parser.py for best practice importing the logger
# from: https://stackoverflow.com/a/15735146
log_filename = "{}_log.{}.txt".format('dr', datetime.datetime.now().strftime('%Y-%m-%d.%H:%M:%S'))
log_directory = "logs"
log_location = os.path.join(log_directory, log_filename)
logging.basicConfig(filename=log_location, level=logging.DEBUG)

def main():
    ''' Manage all the threads, update to async await

    note: preprocess_lines_thread.daemon = True # closes when main thread ends
    '''
    global_game_state = game_state.GlobalGameState()
    tcp_lines = queue.Queue() # split the tcp buffer on '\r\n'
    preprocessed_lines = queue.Queue()
    text_lines = queue.Queue()

    # some issue when writing from submodules, maybe related to file handle, doubt it
    # here we make the file, which may make the handle accessible? worth a shot
    logging.debug("Initating logfile.")


    highlight_list = text_processing.line_config_processor('data/highlights.txt')
    excludes_list = text_processing.line_config_processor('data/excludes.txt')
    
    # player lines is temporary, used to generate a view for urwid_ui
    player_lines = deque() # process the xml into a player log, which can also be a player view

    # TODO: this doesn't seem to work? or if it does, it isn't clean...
    quit_event = threading.Event() # set this flag with quit_event.set() to quit from main thread

    # this should probably be initialized in global_game_state
    # we should probably try to reacquire a socket if we lose it
    gamesock = setup_game_connection.game_connection_controller()

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

    gametime_thread = threading.Thread(target=gametime_incrementor.gametime_incrementer, args=(global_game_state,))
    gametime_thread.daemon = True
    gametime_thread.start()

    # start the UI and UI refresh thread
    # urwid must have its own time.sleep somewhere in its loop, since it doesn't dominate everything
    urwid_ui.urwid_main(global_game_state, player_lines, text_lines, highlight_list, excludes_list, quit_event)


if __name__ == '__main__':
    main()
