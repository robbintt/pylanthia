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

from lxml import etree

import urwid
import urwid_readline

# this is not thread safe... need Queue.Queue
# Queue.Queue uses collections.deque and adds thread safety
from collections import deque
from itertools import islice
# lowercase in python3
import queue

from config import *
from eaccess import get_game_key
from lib import chop_xml_and_text
from lib import get_tcp_lines
from lib import setup_game_connection
from lib import xml_parser

SCREEN_REFRESH_SPEED = 0.1 # how fast to redraw the screen from the buffer
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


def urwid_main():
    ''' just the main process for urwid... needs renamed and fixed up
    '''

    #uc_u = '\u25B2'
    '''
    uc_u = '\u2191'
    uc_d = '\u2193'
    uc_l = '\u2190'
    uc_r = '\u2192'

    uc_ul = '\u2196'
    uc_ur = '\u2197'
    uc_dr = '\u2198'
    uc_dl = '\u2199'
    '''

    # note that these are ordered in Python 3.6+, this assumes you are running 3.6+ !!!
    arrows = {}
    arrows['n'] = 'n'
    arrows['e'] = 'e'
    arrows['s'] = 's'
    arrows['w'] = 'w'
    arrows['nw'] = 'nw'
    arrows['ne'] = 'ne'
    arrows['sw'] = 'sw'
    arrows['se'] = 'se'

    exit_string = ' '
    for k, v in arrows.items():
        if global_game_state.exits.get(k):
            exit_string += v
        else:
            exit_string += ' ' * len(v)  # preserve spacing from glyph
        exit_string += ' '  # separator whitespace

    # consider padding roundtime with 3 spaces
    status_line_string = '[ RT:  {roundtime}{roundtime_stable} ]' + '[{exit_string}]'
    #status_line_string = '[ RT:  {roundtime} ]' + '[ ' + ' '.join([v for k, v in arrows.items()]) + ' ]'

    # imagine a function that adds a space or the arrow depending on
    # whether the compass arrow last received game state
    # currently just used to display them all as a placeholder

    fixed_size_for_now = 30
    main_window = urwid.Text('') # initalize the window empty
    input_box = urwid_readline.ReadlineEdit('> ', '') # pretty sure urwid_readline package needs Python3

    status_line = urwid.Text(status_line_string)

    mainframe = urwid.Pile([
        ('weight', fixed_size_for_now, urwid.Filler(main_window, valign='bottom')),
        ('fixed', 1, urwid.Filler(status_line, 'bottom')),
        ('fixed', 1, urwid.Filler(input_box, 'bottom')),
    ], focus_item=2)

    # these were for the terminal
    def set_title(widget, title):
        mainframe.set_title(title)
    def quit(*args, **kwargs):
        raise urwid.ExitMainLoop()




    def unhandled_input(txt, key):
        ''' 
        
        q: why is this called unhandled input if it is the input handler??
        a: ... urwid thing, this can probably be changed to whatever is appropriate, just use care

        '''

        if key in ("enter"):

            global_game_state.history_scroll_mode = False  # toggle history scroll mode off

            if len(txt.edit_text) == 0:
                ''' ignore an empty command
                '''
                return
            
            submitted_command = txt.edit_text

            # allow multiple commands per line
            # this doesn't work for command history
            # maybe there should be an input history
            global_game_state.input_history.append(submitted_command)
            # replace newlines with semicolons so we can process them homogeneously
            # may need to work with urwid-rlwrap for custom multiline paste features
            # otherwise the major use case for this string replacement is not covered
            submitted_command = submitted_command.replace('\r', ';').replace('\n', ';')
            #logging.info('submitted line:' + submitted_command)

            # use a regex split here so that backslash can escape & 0send semicolon through the prompt
            re_semi_splitter = r'(?<!\\);'
            # replace all backslashes and strip all whitespace from the processed result
            submitted_commands = [c.replace('\\', '').strip() for c in \
                    re.split(re_semi_splitter, submitted_command)]
            #submitted_commands = submitted_command.split(';')

            for _s_c in submitted_commands:
                if len(_s_c) > 0:
                    _s_c = bytes(_s_c, "utf-8")
                    global_game_state.command_queue.put(_s_c)

            txt.set_edit_text('')
            txt.set_edit_pos(0)

            return

        if key in ("up", "down"):

            # deal with the 0 history case here
            if len(global_game_state.input_history) == 0:
                return

            # enter history scroll mode until the user presses enter
            if global_game_state.history_scroll_mode == False:
                global_game_state.history_scroll_mode = True
                global_game_state.input_history_counter = len(global_game_state.input_history) - 1

            # don't do this if you just set it to true! (elif)
            elif global_game_state.history_scroll_mode == True:

                if key in ("up"):
                    if global_game_state.input_history_counter > 0:
                        global_game_state.input_history_counter -= 1

                if key in ("down"):
                    if global_game_state.input_history_counter < len(global_game_state.input_history) - 1:
                        global_game_state.input_history_counter += 1

            input_box.set_edit_text(global_game_state.input_history[global_game_state.input_history_counter])
            input_box.set_edit_pos(len(txt.edit_text))
            return

        if key in ("left"):
            input_box.set_edit_text('')
            input_box.set_edit_pos(len(txt.edit_text))
            return

        if key in ("right"):
            ''' 
            interestingly, because of urwid-readline, i can use right and left arrows
            but only when there is already text on the line, and not on the far edges
            so on the far left, a left key will trigger this
            on the far right, a right key will trigger unknown key: right
            '''
            # need the mutex because this uses a function of the underlying deque
            # see: https://stackoverflow.com/a/6518011
            with global_game_state.rt_command_queue.mutex:
                global_game_state.rt_command_queue.queue.clear()
            return

        # not working
        if key in ("ctrl q", "ctrl Q"):
            #raise urwid.ExitMainLoop()
            quit()

        input_box.set_edit_text("unknown key: " + repr(key))
        input_box.set_edit_pos(len(txt.edit_text))
        return

    '''
    # supposed to fix focus loss, i don't have that issue yet
    # and it may be solved where i set handle_mouse=False in MainLoop
    def mouse_event(self, size, event, button, col, row, focus):
        pass
    '''

    #urwid.connect_signal(term, 'title', set_title)
    #urwid.connect_signal(term, 'closed', quit)

    # reference: http://urwid.org/reference/main_loop.html
    loop = urwid.MainLoop(
        mainframe,
        handle_mouse=False,
        unhandled_input=lambda key: unhandled_input(input_box, key))

    def refresh_screen(loop, player_lines):
        #view_lines_buffer = list() # a buffer of lines sent to the terminal
        while True:
            # ideally we could just check if loop is running
            # is there a data flag on loop we can pause until is True (loop.run() started)

            # do this first so that the urwid MainLoop 'loop' exists! otherwise too fast
            # it would be better to kick this off inside loop.run I think
            time.sleep(SCREEN_REFRESH_SPEED)

            # this really should be in the main thread...
            # urwid has event_loop that can probably handle this
            if quit_event.is_set():
                raise Exception('Client has exited, use exception to cleanup for now.')

            status_line_contents = dict()
            # calculate remaining roundtime
            current_roundtime = int(global_game_state.roundtime - global_game_state.time)
            if current_roundtime < 0:
                current_roundtime = 0
            if current_roundtime < 10:
                # pad < 10
                status_line_contents['roundtime'] = ' ' + str(current_roundtime)
            else:
                # don't pad > 10, note, for roundtimes 100+ there will be a shift in the UI. #wontfix
                status_line_contents['roundtime'] = '' + str(current_roundtime)

            exit_string = ''
            for k, v in arrows.items():
                if global_game_state.exits.get(k):
                    exit_string += v
                else:
                    exit_string += ' ' * len(v)  # preserve spacing from glyph
                exit_string += ' '  # separator whitespace

            status_line_contents['exit_string'] = exit_string

            # show the roundtime stable indicator if both time and roundtime are reported
            # this will be false only when the displayed roundtime is based on projected time
            # (global_game_state.time is projected time)
            if global_game_state.reported_time >= global_game_state.roundtime:
                status_line_contents['roundtime_stable'] = '.'
            else:
                status_line_contents['roundtime_stable'] = ' '

            # format the status line with the current content values
            status_line_output = status_line_string.format(**status_line_contents)

            # set thae status line
            mainframe.contents[1][0].original_widget.set_text(status_line_output)

            # grab at most view_buffer_size lines per refresh
            view_buffer_size = fixed_size_for_now
            # i guess this needs its own buffer. maybe its own function
            # it makes sense for the view contents constructor to be elsewhere anyways
            i = 0
            while i < view_buffer_size:
                # careful this is blocking, if blocked we would want to just return what we have...
                # and even return some stuff from the last buffer attempt too!
                # hmm requires a little thinking!
                # for now we could make it a list and grow it forever...
                # then we can slice the last bit for the view again
                try:
                    new_line = text_lines.get_nowait()
                    # temporarily rebuild player_lines for viewing
                    new_line = b''.join([content for _, content in new_line])
                    player_lines.append(new_line)
                except queue.Empty:
                    # return the player_lines when empty or 'full'/done
                    break
                i += 1

            # slice a view buffer off of player_lines
            # if the view buffer is too long, urwid currently cuts off the bottom, which is terrible... how to fix?
            # can we tap into the current height of the flow widget and give that as the view buffer size?
            # think about it later..
            if len(player_lines) < view_buffer_size:
                _min_slice = 0
            else:
                _min_slice = len(player_lines) - view_buffer_size

            # technique for slicing with a deque
            view_buffer = itertools.islice(player_lines, _min_slice, len(player_lines))
            #view_buffer = player_lines[_min_slice:]


            # ideally a 4000 line buffer view of the current game would be updated elsewhere and just displayed here
            # scrollable would also be really nice
            # right now it just passes the current lines
            main_view_text = b'\n'.join(view_buffer)

            # the contents object is a list of (widget, option) tuples
            # http://urwid.org/reference/widget.html#urwid.Pile
            mainframe.contents[0][0].original_widget.set_text(main_view_text)

            loop.draw_screen()


    # refresh the screen in its own thread.
    refresh = threading.Thread(target=refresh_screen, args=(loop, player_lines))
    refresh.daemon = True # kill the thread if the process dies
    refresh.start()

    loop.run()


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
    urwid_main()



