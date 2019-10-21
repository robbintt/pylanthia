''' A terminal-based python client for dragonrealms

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
from lib import get_tcp_lines

SCREEN_REFRESH_SPEED = 0.1 # how fast to redraw the screen from the buffer
BUF_PROCESS_SPEED = 0.01 # this is a timer for the buffer view creation thread
COMMAND_PROCESS_SPEED = 0.3 # max speed that commands are submitted at
MAX_IDLE_TIME = 60*60*2  # 60*60  # 60 minutes

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


# dump tcp separately
tcplog_filename = "{}_tcplog.{}.txt".format('dr', datetime.datetime.now().strftime('%Y-%m-%d.%H:%M:%S'))
tcplog_directory = "tcplogs"
tcplog_location = os.path.join(log_directory, tcplog_directory, tcplog_filename)

# check this once here, needs to be elsewhere though
if not os.path.exists(tcplog_location):
    with open(tcplog_location, 'w') as f:
        f.write('')


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

        # fix this up
        if elem != root_element:
           continue

        # end parsing when the root element closes
        # what about if there's a tail?
        if action == 'end' and elem is root_element:

            # i could check for a text tail here??
            still_parsing = False

        # lets see some stuff temporarily
        if action == 'end':
            #logging.info("Element processed (action = end):" + elem.tag)
            pass

        e = elem
        # i think i just want to hit the element now, i will iter inside the function if necessary
        #        for e in elem.iter():
        #            ''' iterate over element and all descendants in tree
        #
        #            i can do this without the tag and do actions based on the tag below to parse
        #            all xml... not sure if this is managing <standalone\> elements properly...
        #
        #            use a dict of functions or something here
        #                - do i need to check tag name and attrib dict?
        #            
        #            # in this case the functions still need to handle the attrib dict
        #            xml_actions = { 'popBold' : function1,
        #                            'prompt'  : function2 }
        #
        #            
        #            '''

        def compass(elem):
            ''' get all the dirs inside this

            <compass><dir value="n"/><dir value="e"/><dir value="se"/></compass>

            seems like the xml parser is processing the children seperately too
            '''
            global_game_state.reset_exits()
            for direction in elem.iterchildren('dir'):
                if direction.attrib.get('value'):
                    if direction.attrib.get('value') in list(global_game_state.exits.keys()):
                        global_game_state.exits[direction.attrib.get('value')] = True

            return


        def component(elem):
            ''' needs thought through
            '''
            if elem.attrib.get('id'):
                if elem.attrib['id'] == 'exp':
                    pass

            # catchall
            else:
                text_lines.put((('text', etree.tostring(elem)),)) # tostring is making a bytes string
                text_lines.put((('text', elem.text),)) # tostring is making a bytes string

        def pushBold(elem):
            ''' change this line to a color preset, can hardcode for now
            '''
            #text_lines.put((('text', etree.tostring(e)),)) # tostring is making a bytes string
            return
        
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
            if elem.attrib.get('id'):
                DEBUG_PREFIX = bytes(elem.tag, 'ascii') + b':' + bytes(elem.attrib['id'], 'ascii') + b': '

                if elem.attrib['id'] in ('logons', 'atmospherics'):
                    if elem.tail:
                        text_lines.put('text', elem.tail)
                elif elem.attrib['id'] == 'percWindow':
                    pass
                elif elem.attrib['id'] in ('talk', 'whispers', 'thoughts'):
                    pass
                # catchall for elements WITH 'id' attr
                else:
                    text_lines.put((('text', DEBUG_PREFIX + etree.tostring(elem)),)) # tostring is making a bytes string

            # catchall
            else:
                text_lines.put((('text', b'pushStream: ' + etree.tostring(elem)),)) # tostring is making a bytes string

            return


        def streamWindow(elem):
            ''' room and other stuff
            '''

            if elem.attrib.get('id'):
                if elem.attrib['id'] == 'room':
                    text_lines.put((('text', bytes(elem.attrib['title'] + elem.attrib['subtitle'], 'ascii')),))

            # catchall
            else:
                text_lines.put((('text', b'pushStream: ' + etree.tostring(elem)),)) # tostring is making a bytes string

            return


        def clearStream(elem):
            ''' xml element is not used
            '''
            #text_lines.put((('text', etree.tostring(elem)),)) # tostring is making a bytes string
            return

        def roundTime(elem):
            '''
            '''
            # if they forget roundTime 'value', then we don't update the state
            if elem.attrib.get('value'):
                global_game_state.roundtime = int(elem.attrib.get('value'))
            return

        def prompt(elem):
            '''
            '''
            # if they forget time, then we don't update the state
            if elem.attrib.get('time'):
                global_game_state.reported_time = int(elem.attrib.get('time'))
                global_game_state.time = global_game_state.reported_time
            return

        def preset(elem):
            '''
            '''
            if elem.attrib.get('id'):
                DEBUG_PREFIX = bytes(elem.tag, 'ascii') + b':' + bytes(elem.attrib['id'], 'ascii') + b': '
                if elem.attrib['id'] == 'speech':
                    if elem.text:
                        text_lines.put((('text', bytes(elem.text, 'utf-8')),))
                    pass
                elif elem.attrib['id'] == 'roomDesc':
                    logging.info(b"room text: " + etree.tostring(elem))
                    #logging.info(b"room text: " + bytes(elem, 'ascii'))
                    #line = (('text', elem.text),)
                    #text_lines.put(line)
                    text_lines.put((('text', etree.tostring(elem)),))
                    pass
                #attrib == id catchall
                else:
                    pass
                    text_lines.put((('text', DEBUG_PREFIX + etree.tostring(elem)),)) # tostring is making a bytes string

            # catchall
            else:
                text_lines.put((('text', b'preset no id:' + etree.tostring(elem)),)) # tostring is making a bytes string
                pass
            return


        def dialogData(elem):
            '''
            '''
            if elem.attrib.get('id'):
                if elem.attrib['id'] == 'minivitals':
                    pass
                #attrib == id catchall
                else:
                    text_lines.put((('text', etree.tostring(elem)),)) # tostring is making a bytes string

            # catchall
            else:
                text_lines.put((('text', etree.tostring(elem)),)) # tostring is making a bytes string
            return


        def style(elem):
            '''
            '''
            if elem.attrib.get('id'):
                if elem.attrib['id'] == 'roomName':
                    pass
                if elem.attrib['id'] == '':
                    pass

            # catchall
            else:
                text_lines.put((('text', b'style: ' + etree.tostring(elem)),)) # tostring is making a bytes string
            return

        def resource(elem):
            '''
            '''
            if elem.attrib.get('picture'):
                pass

            # catchall
            else:
                text_lines.put((('text', etree.tostring(elem)),)) # tostring is making a bytes string
            return


        # you would use if statements on the attribs inside
        # attribs can always be passed as elem.attrib in this format
        xml_actions = { 'roundTime'  : roundTime,
                        'prompt'  : prompt,
                        'popStream' : popStream,
                        'compass' : compass,
                        'component' : component,
                        'resource' : resource,
                        'preset' : preset,
                        'style' : style,
                        'dialogData' : dialogData,
                        # if i enable pushstream then it eats up the rest of the input
                        # this is just one example of how i need to redo the xml parsing
                        'pushStream' : pushStream,
                        'streamWindow' : streamWindow,
                        'clearStream' : clearStream,
                        'popBold' : popBold,
                        'pushBold' : pushBold }

        # run the function at e.tag
        # if there isn't a tag just skip it... 
        if xml_actions.get(e.tag, None):
            logging.info("found function for {}: {}".format(e.tag, xml_actions[e.tag]))
            try:
                xml_actions[e.tag](e)
            # we need to globally handle exceptions gracefully without crashing
            # i think this raise will eventually pass the exception up to the handler
            except Exception as exc:
                raise exc
        else:
            # interestingly, this is still getting child xml to parse...
            # even though the xml feeder is still correctly feeding it inside the parent
            # intentionally still passing: popBold
            # for now: put all xml lines not in xml_actions
            logging.info(b"XML Parse Failed:RAW=" + etree.tostring(e))
            #text_lines.put((('text', b'RAW:' + etree.tostring(e)),)) # tostring is making a bytes string
            # we could do something custom here, like log the missing xml_action for later use
            pass

        # is this universally true?
        if e.tail:
            text_lines.put((('text', 'tail: ' + e.tail.encode('utf-8')),))


    return root_element, still_parsing


def process_game_xml(preprocessed_lines, text_lines):
    ''' Get any game state out of the XML, return a replacement line
    
    We now want to process any XML line fully as xml using the obj.text and obj.tail values
    to retrieve text.

    RULE:
        1. If a line starts with XML it is XML
        2. Otherwise, it is text.

    This RULE greatly simplifies parsing and removes us from split text/xml lines.

    It's a complicated rewrite, but should present a flatter control flow.

    Some XML elements are always multiline and we want to be able to parse those as a single glob.

    The failure state (xml not processed) should leave the XML in the display, so the
    player can report the issue and work around it without missing an important detail.

    '''
    # Queue.get() blocks by default
    op_line = preprocessed_lines.get()

    # don't process if it doesn't start with XML
    # this may not be a hard and fast rule, mid-line XML might be a thing
    # if so update this control flow
    if op_line and op_line[0][0] != 'xml':

        try:
            # don't use this to trigger the command queue, use the global roundtime time
            pattern_command_failed = r'\.\.\.wait ([0-9]+) seconds\.'
            line = op_line[0][1].decode('utf-8')
            # how costly is this? it should compile/cache the re string... 
            # should we check the `...` string segment before testing the re?
            # deal with later as necessary
            command_failed = re.fullmatch(pattern_command_failed, line) 
            # hopefully we can grab the last command
            # you can imagine how this would fail if 2 commands were submitted back to back
            # so it's not this simple, we need to be able to give commands some index
            # but lets not YET add a bigger data structure for each command in the command history - YET
            if command_failed:
                failing_command = global_game_state.command_history.get()
                logging.info(b'Command failed from RT: ' + failing_command)
                global_game_state.rt_command_queue.put(failing_command)
        except Exception as e:
            logging.info("failed: ", e)


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

        # if the line is text...
        else:
            text_lines.put((op_line[linenum],))


        linenum += 1

        # feed another line if still parsing
        # probably need a cap on how many times we will do this before dumping the xml and moving on
        if linenum >= len(op_line) and still_parsing:
            op_line.append(preprocessed_lines.get())

    
    ## once the line is processed, trigger all queued xml events for the line?
    ## we can also trigger the xml events as they come up...

    return


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
    '''
    global_game_state = GlobalGameState()

    tcp_lines = queue.Queue() # split the tcp buffer on '\r\n'
    preprocessed_lines = queue.Queue()
    text_lines = queue.Queue()
    player_lines = deque() # process the xml into a player log, which can also be a player view

    quit_event = threading.Event() # set this flag with quit_event.set() to quit from main thread

    GAME_KEY = get_game_key(eaccess_host, eaccess_port, username, password)

    # hopefully we can reuse this to reload the game if it breaks
    gamesock = setup_game_connection(server_addr, server_port, GAME_KEY, frontend_settings)

    preprocess_lines_thread = threading.Thread(target=preprocess_tcp_lines, args=(tcp_lines, preprocessed_lines))
    preprocess_lines_thread.daemon = True # closes when main thread ends
    preprocess_lines_thread.start()

    process_lines_thread = threading.Thread(target=process_lines, args=(preprocessed_lines, text_lines))
    process_lines_thread.daemon = True # closes when main thread ends
    process_lines_thread.start()

    tcp_thread = threading.Thread(target=get_tcp_lines.get_tcp_lines, args=(tcp_lines, tcplog_location, gamesock))
    tcp_thread.daemon = True #  closes when main thread ends
    tcp_thread.start()

    command_queue_thread = threading.Thread(target=process_command_queue, args=(global_game_state, tcp_lines))
    command_queue_thread.daemon = True #  closes when main thread ends
    command_queue_thread.start()

    gametime_thread = threading.Thread(target=gametime_incrementer, args=(global_game_state,))
    gametime_thread.daemon = True #  closes when main thread ends
    gametime_thread.start()

    # start the UI and UI refresh thread
    # urwid must have its own time.sleep somewhere in its loop, since it doesn't dominate everything
    urwid_main()



