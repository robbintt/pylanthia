'''
'''
import socket
import threading

import time
import itertools
import re

import urwid
import urwid_readline

from collections import deque
from config import *

import datetime
import logging

import os


log_filename = "{}_log.{}.txt".format('dr', datetime.datetime.now().strftime('%y%m%d%H%M%S'))
log_directory = "logs"
log_location = os.path.join(log_directory, log_filename)

logging.basicConfig(filename=log_location, level=logging.INFO)


BUFSIZE = 32 # adjust based on actual data for dr buffers

EXCLUDES = [
    r'<prompt.*>',
    r'</prompt.*>',
]

SUBS = [
    (r'<.*>', ''),
]


def filter_lines(view_lines):
    ''' this was temporary and needs rebuilt with some terminal editable filter

    would be good to be able to add filters, view filters by index, and delete filters

    good use for file or sqlite database... file is nice as users can share, can call a reload function
    '''

    excludes = ['<prompt time="']

    # this still doesn't work because we need to filter xml above the line level
    # do newlines from the server ever contain meaningful data or are they pointless?
    # is all the newline data given by a terminating xml-type tag?

    # filter lines that start with an exclude string - non-regex
    for exclude in excludes:
        view_lines = [line for line in view_lines if line[0:len(exclude)] != exclude]


    '''
    # drop empty lines before the regex to save processing
    # what about lines with whitespace only...
    view_lines = [line for line in view_lines if line != b'' or line != b'&gt']

    for exclude in EXCLUDES:
        view_lines = [str(line) for line in view_lines if not re.search(exclude, str(line))]

    for expr, sub in SUBS:
        view_lines = [re.sub(expr, sub, str(line)) for line in view_lines]

    # drop empty lines after the regex so they aren't shown
    view_lines = [line for line in view_lines if line != b'' or line != b'&gt']
    '''

    return view_lines


sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server = (server_addr, int(server_port))
sock.connect(server)

time.sleep(1) # would be better to get an ACK of some sort before sending the token...
sock.sendall(server_login_token)
sock.sendall(b'\n')
sock.sendall(frontend_setting)
sock.sendall(b'\n')

tcp_lines = deque()
new_tcp_lines = True

# needs a second to connect or else it hangs, then you need to send a newline or two...
time.sleep(1)
sock.sendall(b'\n')
sock.sendall(b'\n')

def get_tcp_lines():
    ''' receive text and xml into a buffer and split on newlines
    '''
    view_buffer = bytes()
    while True:
        res = sock.recv(BUFSIZE)
        view_buffer += res
        if b'\n' in view_buffer:
            new_tcp_lines = True # maybe trigger the refresh here...
            tcp_lines.extend(view_buffer.split(b'\r\n'))
            view_buffer = tcp_lines.pop() # leave the last line, it's normally not cooked
        else:
            new_tcp_lines = False

tcp_thread = threading.Thread(target=get_tcp_lines)
tcp_thread.daemon = True # close with main thread
tcp_thread.start()


'''
# pass this between a bunch of threads
increasing_text = list()

def grow_text():
    i = 0
    while True:
        increasing_text.append(str(i)+'\n')
        import time; time.sleep(1)
        i += 1

t = threading.Thread(target=grow_text)
t.daemon = True # daemon threads die when non-daemon/main thread exits
t.start()
'''


def main():

    # wrap the top text widget with a flow widget like Filler: https://github.com/urwid/urwid/wiki/FAQ
    main_window = urwid.Text('\r\n'.join(tcp_lines))
    input_box = urwid_readline.ReadlineEdit('> ', '') # pretty sure this needs Python3
    mainframe = urwid.Pile([
        ('weight', 70, urwid.Filler(main_window, valign='bottom')),
        ('fixed', 1, urwid.Filler(input_box, 'bottom')),
    ], focus_item=1)

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
            tcp_lines.append(b'> ' + submitted_command)

            txt.set_edit_text('')
            txt.set_edit_pos(0)

            # not sure if sending this has a buffer? or is it lag in the receive side...
            sock.sendall(submitted_command + b'\n')
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

    REFRESH_SPEED = 0.1
    def refresh_screen(loop, user_data=None):
        view_lines_buffer = list() # a buffer of lines sent to the terminal
        while True:
            # ideally we could just check if loop is running
            # is there a data flag on loop we can pause until is True (loop.run() started)

            # do this first so that loop exists! otherwise too fast
            time.sleep(REFRESH_SPEED)

            # the contents object is a list of (widget, option) tuples
            # http://urwid.org/reference/widget.html#urwid.Pile

            # currently just smash up the tcp line history, but need to change that
            view_lines_buffer.extend(tcp_lines)
            tcp_lines.clear()
            mainframe.contents[0][0].original_widget.set_text(
                    b'\n'.join(filter_lines(view_lines_buffer[-50:])))

            loop.draw_screen()


    # alternative approach to stick refresh in a thread ourselves
    refresh = threading.Thread(target=refresh_screen, args=(loop,))
    refresh.daemon = True # daemon mode
    refresh.start()

    # alarm callback: https://stackoverflow.com/questions/12044463/urwid-doesnt-update-screen-on-loop-draw-screen
    # i think this takes over in this thread which ruins what i am doing
    # i guess this calls the callback function, refresh_screen, in another thread
    # this doesn't work because it clogs up the main thread
    #loop.set_alarm_in(REFRESH_SPEED, refresh_screen)

    loop.run()


if __name__ == '__main__':
    main()
