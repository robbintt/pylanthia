'''
'''
import time
import threading
import queue
import itertools
import re
import textwrap

import urwid
import urwid_readline
from urwid_stackedwidget import StackedWidget

from vendor.scroll.scroll import ScrollBar, Scrollable

import logging
logging.getLogger(__name__)

def extend_view_buffer(text_deque, target_queue, highlight_list, excludes_list):
    '''
    # it makes sense for the view contents constructor to be elsewhere anyways
    this probably belongs somewhere else
    '''
    i = 0
    max_lines_per_refresh = 50 # not sure if this is necessary
    while not target_queue.empty() and i < max_lines_per_refresh:
        new_line = target_queue.get()

        # munge new_line and convert bytes->utf-8
        new_line_str = b''.join([content for _, content in new_line]).decode('utf-8')+'\n'

        _skip_excluded_line = False
        for exclude_substr in excludes_list:
            if exclude_substr in new_line_str:
                _skip_excluded_line = True  # set flag to continue parent
                break
        if _skip_excluded_line == True:
            continue

        for highlight in highlight_list:
            if highlight in new_line_str:
                new_line_str = ('highlight', new_line_str)
                break # i guess just 1 highlight per string for now
                # write a recursive function? what about substrings?
                # there needs to be a color mask or something on the string index
                # (white, 5, 7), (red, 6, 7) - apply in order so last gets precedence, use python slice positional

        #game_state.urwid_views['urwid_main_view'].append(new_line_str)
        # rolls item 0 out on append due to deque maxlen
        text_deque.append(new_line_str)
        i += 1

    return


def urwid_main(game_state, text_lines, chat_lines, highlight_list, excludes_list, quit_event, screen_refresh_speed=0.05):
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

    color_palette = [
        ('banner', '', '', '', '#fff', 'g35'),
        ('statusbar', 'white', 'black'),
        ('highlight', 'white', '', '', 'g0', 'g35'),
        ('white', 'white', '', '', 'g0', 'g35'),
        ('inside', '', '', '', 'g0', 'g35'),
        ('outside', '', '', '', 'g0', 'g35'),
        ('bg', '', '', '', 'g35', '#fff'),]

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
        if game_state.exits.get(k):
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

    fixed_size_for_now = 1000
    main_window_buffer_size = 40
    main_window_stack = StackedWidget()

    # must be initalized with an empty string
    # these should probably go in a map instead of hardcoded...
    # probably want to map N xml-defined tags to M message deques
    story_window = ScrollBar(Scrollable(urwid.Text('')))
    tcp_window = ScrollBar(Scrollable(urwid.Text('')))
    chat_window = ScrollBar(Scrollable(urwid.Text('')))

    main_window_stack.push_widget(story_window)
    main_window_stack.push_widget(tcp_window)
    main_window_stack.push_widget(chat_window)

    input_box = urwid_readline.ReadlineEdit('> ', '') # pretty sure urwid_readline package needs Python3

    status_line = urwid.Text(status_line_string)

    mainframe = urwid.Pile([
        ('weight', fixed_size_for_now, urwid.Filler(main_window_stack, height=main_window_buffer_size, valign='bottom')),
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
        much of this input should be handled in the pile or widgets inside the pile
        
        q: why is this called unhandled input if it is the input handler??
        a: ... urwid thing, this can probably be changed to whatever is appropriate, just use care

        '''
        if key in ("`"):
            if main_window_stack.current + 1 >= main_window_stack.widget_count:
                main_window_stack.current = 0
            else:
                # don't use the fake setter, it's doing some weird modulo stuff
                # maybe after reviewing the module code more...
                main_window_stack.current += 1

        if key in ("tab"):
            # rudimentary focus bouncer for now
            # ideally focus bounce will toggle buffers in the future
            if mainframe.focus_position == 2:
                mainframe.focus_position = 0
            else:
                mainframe.focus_position = 2
            return

        if key in ("enter"):

            game_state.history_scroll_mode = False  # toggle history scroll mode off

            if len(txt.edit_text) == 0:
                ''' ignore an empty command
                '''
                return
            
            submitted_command = txt.edit_text

            # used to have a command splitter here, decided not to use it
            game_state.input_history.append(submitted_command)
            game_state.command_queue.put(submitted_command.encode('utf-8'))

            txt.set_edit_text('')
            txt.set_edit_pos(0)

            return

        if key in ("up", "down"):

            # deal with the 0 history case here
            if len(game_state.input_history) == 0:
                return

            # enter history scroll mode until the user presses enter
            if game_state.history_scroll_mode == False:
                game_state.history_scroll_mode = True
                game_state.input_history_counter = len(game_state.input_history) - 1

            # don't do this if you just set it to true! (elif)
            elif game_state.history_scroll_mode == True:

                if key in ("up"):
                    if game_state.input_history_counter > 0:
                        game_state.input_history_counter -= 1

                if key in ("down"):
                    if game_state.input_history_counter < len(game_state.input_history) - 1:
                        game_state.input_history_counter += 1

            input_box.set_edit_text(game_state.input_history[game_state.input_history_counter])
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
            with game_state.rt_command_queue.mutex:
                game_state.rt_command_queue.queue.clear()
            return

        # not working
        if key in ("ctrl q", "ctrl Q"):
            #raise urwid.ExitMainLoop()
            quit()


        #input_box.set_edit_text("unknown key: " + repr(key))
        #input_box.set_edit_pos(len(txt.edit_text))
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
        color_palette,
        handle_mouse=False,
        unhandled_input=lambda key: unhandled_input(input_box, key))

    def refresh_screen(game_state, loop):
        #view_lines_buffer = list() # a buffer of lines sent to the terminal
        while True:
            # ideally we could just check if loop is running
            # is there a data flag on loop we can pause until is True (loop.run() started)

            # do this first so that the urwid MainLoop 'loop' exists! otherwise too fast
            # it would be better to kick this off inside loop.run I think
            time.sleep(screen_refresh_speed)

            # this really should be in the main thread...
            # urwid has event_loop that can probably handle this
            if quit_event.is_set():
                raise Exception('Client has exited, use exception to cleanup for now.')

            status_line_contents = dict()
            # calculate remaining roundtime
            current_roundtime = int(game_state.roundtime - game_state.time)
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
                if game_state.exits.get(k):
                    exit_string += v
                else:
                    exit_string += ' ' * len(v)  # preserve spacing from glyph
                exit_string += ' '  # separator whitespace

            status_line_contents['exit_string'] = exit_string

            # show the roundtime stable indicator if both time and roundtime are reported
            # this will be false only when the displayed roundtime is based on projected time
            # (game_state.time is projected time)
            if game_state.reported_time >= game_state.roundtime:
                status_line_contents['roundtime_stable'] = '.'
            else:
                status_line_contents['roundtime_stable'] = ' '

            # format the status line with the current content values
            status_line_output = status_line_string.format(**status_line_contents)
            # set the status line
            mainframe.contents[1][0].original_widget.set_text(('statusbar', status_line_output))

            # fill up the urwid main view text
            if not text_lines.empty():
                extend_view_buffer(game_state.urwid_views['urwid_main_view'], text_lines, highlight_list, excludes_list)
            # fill up the urwid chat view text
            if not chat_lines.empty():
                extend_view_buffer(game_state.urwid_views['urwid_chat_view'], chat_lines, highlight_list, excludes_list)

            # this target is one below main_window so lets try that instead
            # mainframe is the pile, contents[0] is the first item
            #scrollable_textbox = mainframe.contents[0][0].original_widget.current_widget._original_widget
            # this one is dynamic based on active stacked window
            current_main_window = mainframe.contents[0][0].original_widget.current_widget._original_widget
            # scrollable_textbox = story_window._original_widget

            # we can use python names instead of drilling down...
            #    - this is critical to future urwid organization
            # the contents object is a list of (widget, option) tuples
            # http://urwid.org/reference/widget.html#urwid.Pile
            # apparently it will not take a deque, so coerce to a list
            story_window._original_widget._original_widget.set_text(list(game_state.urwid_views['urwid_main_view']))
            tcp_window._original_widget._original_widget.set_text(list(game_state.urwid_views['urwid_tcp_view']))
            chat_window._original_widget._original_widget.set_text(list(game_state.urwid_views['urwid_chat_view']))

            # MUST - scroll the active window
            # scroll unless item 0 is in focus - is item 0 the filler?
            if mainframe.focus_position != 0:
                # set and record the most recent position
                current_main_window.set_scrollpos(-1)
                game_state.urwid_scrollbar_last = current_main_window.get_scrollpos()

            loop.draw_screen()


    # refresh the screen in its own thread.
    # this camn probably get moved to main() in pylanthia.py
    refresh = threading.Thread(target=refresh_screen, args=(game_state, loop))
    refresh.daemon = True # kill the thread if the process dies
    refresh.start()

    loop.run()
