''' A terminal-based python client for dragonrealms

The client is implemented with socket and urwid.

Global variables may not yet be locked properly for threading,
especially when appending sent text to the stream.

There is some confusion about how much information newlines from the
server actually hold. The server does not seem to provide newlines between
consecutive xml tags so some data needs to be extracted from the stream

The stream can also be logged directly and replayed in order to test certain behavior.
This is probably the best place to start.

Processing steps before player sees lines:

    1. convert xml lines to events or 'window streams'
        - some streams:
            - room
            - backpack
            - inventory
            - health snapshot
            - roundtime
            - prompt/time
            - logins, logouts
            - deaths, raises, etc?
    3. 'ignore filter' the lines
        - a line is ignored if a substring is found in it
    4. 'color filter' the lines: 
        - substring search, potential for regex search
        - a line can be colored or just the substring/regex section of the string
        - need conversion of hex colors downscaled for terminal? mapping?
        - customize background and foreground color, per-character basis
    5. need persistent data structure to store 'ignore filters' and 'color filters'
        - SQLite or flat config file
        - maybe a flat config file at first so it can be configured outside the game
        - ability to hot reload the flat config
        - how will a player use filters to create new streams?
            - this is a killer feature


TCP Lines:
    - tcp lines are logged by appending to a file

Display lines:
    - player display lines should be displayed and logged after all processing
    - processing could all occur in the same thread?
    - Where are display lines consumed?
        - urwid loop thread
        - logging method?




TODO:
    - log per character name
    - make a 'last played' log that is easier to tail for debugging and building xml
    - separate xml parsing into its own data structure, consider sqlite if huge



'''
import socket
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

TCP_BUFFER_SLEEP = 0.01 # not sure if i want to sleep this or not
SCREEN_REFRESH_SPEED = 0.1 # how fast to redraw the screen from the buffer
BUF_PROCESS_SPEED = 0.01 # this is a timer for the buffer view creation thread
BUFSIZE = 16 # This seems to give a better response time than 128 bytes

# set up logging into one place for now
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
        self.time = 0


# dump tcp separately
tcplog_filename = "{}_tcplog.{}.txt".format('dr', datetime.datetime.now().strftime('%Y-%m-%d.%H:%M:%S'))
tcplog_directory = "tcplogs"
tcplog_location = os.path.join(log_directory, tcplog_directory, tcplog_filename)

# check this once here, needs to be elsewhere though
if not os.path.exists(tcplog_location):
    with open(tcplog_location, 'w') as f:
        f.write('')


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

        # only process a line if one exists
        # don't really need this check since Queue.get() is blocking by default
        # may want it to give a spinning wheel/timeout in the else
        if not preprocessed_lines.empty():
            process_game_xml(preprocessed_lines, text_lines)
        else:
            pass

        # this sleep throttles max line processing speed
        # it doesn't gate tcp_lines.get() because that function will wait on its own.
        time.sleep(BUF_PROCESS_SPEED)


def parse_events(parser, root_element, still_parsing):
    ''' When an element ends, determine what to do

    these functions govern what is put in the text_lines Queue
    e.g. text_lines.put(whatever)

    A lot of data is given to the user by XML - store it in game state object
        - quick health
        - roundtime
        - inventory? some...
        - room contents
        - assess


    scenarios:
    1. For certain xml root tags, we want to grab multiline
        - which elements? we need a catalog
    2. For others, we just want part of the line
        - this is the default, just stop when you have the tag


    '''
    
    for action, elem in parser.read_events():

        # store the root element so we can check when it closes
        if root_element is None:
            root_element = elem

        # end parsing when the root element closes
        if action == 'end' and elem is root_element:
            still_parsing = False

        # lets see some stuff temporarily
        if action == 'end':
            #logging.info("Element processed (action = end):" + elem.tag)
            pass


        for e in elem.iter():
            ''' iterate over element and all descendants in tree

            i can do this without the tag and do actions based on the tag below to parse
            all xml... not sure if this is managing <standalone\> elements properly...

            use a dict of functions or something here
                - do i need to check tag name and attrib dict?
            
            # in this case the functions still need to handle the attrib dict
            xml_actions = { 'popBold' : function1,
                            'prompt'  : function2 }

            
            '''
            # not yet used // just an idea
            class XMLActions():
                ''' better as a dict or class

                i do like the strings as keys

                dot notation is not as if loading the xml->control flow
                from a database since it's a string anyways

                especially if i store the xml in a sqlite database
                '''
                def __init__(self):
                    pass

            xml_actions_object = XMLActions()

            
            def popBold(elem):
                ''' xml element is not used
                '''
                logging.info("popBold: " + repr(elem.attrib))
                return

            def popStream(elem):
                ''' xml element is not used
                '''
                logging.info("popStream: " + repr(elem.attrib))
                return

            def pushStream(elem):
                ''' 
                this xml element needs to grab more lines until it finds <popStream/>
                notably used for streamWindow / id='inv' on startup

                '''
                logging.info("pushStream: " + repr(elem.attrib))

                if elem.attrib.get('id'):
                    if elem.attrib[id] == 'logons':
                        if elem.tail:
                            text_lines.put(elem.tail)

                return

            def clearStream(elem):
                ''' xml element is not used
                '''
                logging.info("clearStream: " + repr(elem.attrib))
                return

            def roundTime(elem):
                '''
                '''
                logging.info("roundTime: " + repr(elem.attrib))
                # if they forget roundTime 'value', then we don't update the state
                if elem.attrib.get('value'):
                    global_game_state.roundtime = int(elem.attrib.get('value'))
                return

            def prompt(elem):
                '''
                '''
                # if they forget time, then we don't update the state
                if elem.attrib.get('time'):
                    global_game_state.time = int(elem.attrib.get('time'))
                return

                

            # you would use if statements on the attribs inside
            # attribs can always be passed as elem.attrib in this format
            xml_actions = { 'roundTime'  : roundTime,
                            'prompt'  : prompt,
                            'popStream' : popStream,
                            # if i enable pushstream then it eats up the rest of the input
                            # this is just one example of how i need to redo the xml parsing
                            #'pushStream' : pushStream,
                            #'clearStream' : clearStream,
                            'popBold' : popBold }

            # run the function at e.tag
            # if there isn't a tag just skip it... 
            if xml_actions.get(e.tag, None):
                logging.info("found function for {}: {}".format(e.tag, xml_actions[e.tag]))
                xml_actions[e.tag](e)
            else:
                # intentionally still passing: popBold
                # for now: put all xml lines not in xml_actions
                logging.info(type(etree.tostring(e)))
                text_lines.put((('text', etree.tostring(e)),)) # tostring is making a bytes string
                # we could do something custom here, like log the missing xml_action for later use
                pass

            # is this universally true?
            if e.tail:
                text_lines.put((('text', e.tail.encode('utf-8')),))


    return root_element, still_parsing


def process_game_xml(preprocessed_lines, text_lines):
    ''' Get any game state out of the XML, return a replacement line

    I think I'll need an empty line filter after this, since game state will often
    return nothing except in a UI indicator. Don't go too far with this though since
    lines will also be filtered into streams for composition by users.

    This is a temporary function, it will probably end up being an object that has the
    ability to hold a line and request more lines. Some XML elements are always
    multiline and we want to be able to parse those as a single glob.

    The failure state (xml not processed) should leave the XML in the display, so the
    player can report the issue and work around it without missing an important detail.

    is this relevant anymore?:
        # commented rebuilt line for now bc we're individually pulling each op_line tag
        # rebuilt_line = b''.join(x[1] for x in op_line)

    '''
    # Queue.get() blocks by default
    op_line = preprocessed_lines.get()

    # don't process if it doesn't start with XML
    # this may not be a hard and fast rule, mid-line XML might be a thing
    # if so update this control flow
    if op_line and op_line[0][0] != 'xml':
        text_lines.put(op_line)
        return


    # i think there are some multiline xml objects, need to review the TCP dumps
    # if so, we can just say "if still_parsing: op_line.append(preprocessed_lines.get())
    # this is a straightforwards way to get a multiline string.
    # it doesn't solve hypothetical cases where a self-closing tag has text after and then
    # another self-closing tag symbolizes the end of that text.  - catalog these manually!
    # run each line as its own xml... but this is a disaster as some have closing tags!
    linenum = 0
    while linenum < len(op_line):

        nextline = op_line[linenum][1]

        # only feed the line if it starts with xml... is this universally true?
        if op_line[linenum][0] == 'xml':

            '''
            # identify if the root xml element has a text tail. if so, append it.
            # this allows us to munge the text element.tail in the element's 'action' function
            # *** needs doing *** warning: only self-closing tags have text tails... how to manage this?
            # *** could label self closing elements in the splitter differently...
            # *** note: since non-self-closing-elements never have a tail, this "should not" break things...
            if linenum+1 < len(op_line) and op_line[linenum+1][0] == 'text':
                linenum += 1
                tail = op_line[linenum][1]
                nextline += tail
            '''

            events = ('start', 'end',) # other events might be useful too? what are my options?
            parser = etree.XMLPullParser(events, recover=True) # can we log recoveries somewhere?
            
            # feed lines until the root element is closed
            root_element = None
            still_parsing = True
            while still_parsing and linenum < len(op_line):

                # the initial nextline is already set up, see directly above
                if not nextline:
                    nextline = op_line[linenum][1] # same as line, but used/incremented in this while loop
                parser.feed(nextline)

                # examine the parser and determine if we should feed more lines or close...
                root_element, still_parsing = parse_events(parser, root_element, still_parsing)
                
                # avoid double increment in parent while loop
                if still_parsing:
                    linenum += 1

                nextline = b''

            #parser.close() # i think this is recommended... read about it, it is probably gc'd next loop?

        linenum += 1

        # feed another line if still parsing
        # probably need a cap on how many times we will do this before dumping the xml and moving on
        if linenum >= len(op_line) and still_parsing:
            op_line.append(preprocessed_lines.get())

    
    ## once the line is processed, trigger all queued xml events for the line?
    ## we can also trigger the xml events as they come up...

    return


def get_tcp_lines():
    ''' receive text and xml into a buffer and split on newlines

    this function does lock tcp_lines
    do we need a timer to give it back to the GIL?

    this thing does not sleep, i don't think it needs to
    the socket waits around a lot
    '''
    tcp_buffer = bytes()
    while True:
        tcp_chunk = gamesock.recv(BUFSIZE)

        # this is kind of a lot of writes... should be fine though
        with open(tcplog_location, 'a') as f:
            f.write(tcp_chunk.decode('utf-8'))

        # the buffer could f.read the last 4000 characters or something.. what's faster?
        # right now the buffer grows without limit, which is not the best...
        tcp_buffer += tcp_chunk

        if b'\n' in tcp_buffer:
            tcp_buffer_by_lines = tcp_buffer.split(b'\r\n')
            # grab the last one back
            tcp_buffer = tcp_buffer_by_lines.pop()
            # store the rest on the queue
            for line in tcp_buffer_by_lines:
                tcp_lines.put(line)
                    
            #logging.info("tcp lines processed: {}".format(len(tcp_buffer)))
        else:
            #logging.info("tcp line has no newline: {}".format(tcp_buffer))
            time.sleep(TCP_BUFFER_SLEEP)
            pass


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

    # will want to assign an order to directions, once settled on a display method
    arrows = {}
    arrows['n'] = 'n'
    arrows['e'] = 'e'
    arrows['s'] = 's'
    arrows['w'] = 'w'
    arrows['nw'] = 'nw'
    arrows['ne'] = 'ne'
    arrows['sw'] = 'sw'
    arrows['se'] = 'se'

    status_line_string = '[ RT:  {roundtime} ]' + '[ ' + ' '.join([v for k, v in arrows.items()]) + ' ]'

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

    '''
    def handle_key(key):
        if key in ('q', 'Q'):
            quit()
    '''
    

    def unhandled_input(txt, key):
        ''' why is this called unhandled input if it is the input handler??
        '''
        if key in ("enter"):
            # this really should be in some 'handled_input' function or something
            submitted_command = bytes(txt.edit_text, "utf-8")
            logging.info(submitted_command)

            # maybe timestamped as its own output stream, so it can be turned off on certain windows
            # this should actually go in player lines, not muddy up the tcp input...
            tcp_lines.put(b'> ' + submitted_command)

            txt.set_edit_text('')
            txt.set_edit_pos(0)

            # not sure if sending this has a buffer? or is it lag in the receive side...
            gamesock.sendall(submitted_command + b'\n')
            if submitted_command in [b'exit', b'quit']:
                raise Exception("Client has exited, use exception to cleanup for now.")
            return

        if key in ("ctrl q", "ctrl Q"):
            #raise urwid.ExitMainLoop()
            quit()

        input_box.set_edit_text("unknown key: " + repr(key))
        input_box.set_edit_pos(len(txt.edit_text))

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


            status_line_contents = dict()
            # calculate remaining roundtime
            current_roundtime = int(global_game_state.roundtime - global_game_state.time)
            if current_roundtime < 0:
                current_roundtime = 0
            status_line_contents['roundtime'] = current_roundtime

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


def setup_game_connection(server_addr, server_port, key, frontend_settings):
    ''' initialize the connection and return the game socket
    '''

    gamesock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server = (server_addr, int(server_port))
    gamesock.connect(server)

    time.sleep(1) # would be better to get an ACK of some sort before sending the token...
    gamesock.sendall(key)
    gamesock.sendall(b'\n')
    gamesock.sendall(frontend_settings)
    gamesock.sendall(b'\n')

    # needs a second to connect or else it hangs, then you need to send a newline or two...
    time.sleep(1)
    gamesock.sendall(b'\n')
    gamesock.sendall(b'\n')

    return gamesock


def gametime_incrementer(global_game_state):
    '''
    '''
    while True:
        time.sleep(1)

        # this is incremented since we only get gametime about every 5-20 seconds
        global_game_state.time += 1


if __name__ == '__main__':
    ''' Set up the connection and start the threads
    '''
    global_game_state = GlobalGameState()

    tcp_lines = queue.Queue() # split the tcp buffer on '\r\n'
    preprocessed_lines = queue.Queue()
    text_lines = queue.Queue()
    player_lines = deque() # process the xml into a player log, which can also be a player view
    
    GAME_KEY = get_game_key(eaccess_host, eaccess_port, username, password)

    # hopefully we can reuse this to reload the game if it breaks
    gamesock = setup_game_connection(server_addr, server_port, GAME_KEY, frontend_settings)

    preprocess_lines_thread = threading.Thread(target=preprocess_tcp_lines, args=(tcp_lines, preprocessed_lines))
    preprocess_lines_thread.daemon = True # closes when main thread ends
    preprocess_lines_thread.start()

    process_lines_thread = threading.Thread(target=process_lines, args=(preprocessed_lines, text_lines))
    process_lines_thread.daemon = True # closes when main thread ends
    process_lines_thread.start()

    tcp_thread = threading.Thread(target=get_tcp_lines)
    tcp_thread.daemon = True #  closes when main thread ends
    tcp_thread.start()

    gametime_thread = threading.Thread(target=gametime_incrementer, args=(global_game_state,))
    gametime_thread.daemon = True #  closes when main thread ends
    gametime_thread.start()

    # start the UI and UI refresh thread
    # urwid must have its own time.sleep somewhere in its loop, since it doesn't dominate everything
    urwid_main()



