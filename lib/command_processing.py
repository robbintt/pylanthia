"""
"""
import time
import re
import logging

logging.getLogger(__name__)

from lib import text_processing

def process_command_queue(game_state, tcp_lines, gamesock, COMMAND_PROCESS_SPEED=0.3):
    """ process game commands from the submit queue

    need some hotkey to dump the queue

    don't process for n seconds if you got the response: "...wait <n> seconds."
    """
    while True:

        # this sleep throttles max command processing speed
        time.sleep(COMMAND_PROCESS_SPEED)

        # this process is already exited, we need to check the health of the lich process
        # maybe lich launcher process could return the pid for lich
        # then we could poll the pid and if not alive, exit
        # if game_state.lichprocess.poll() is not None:
        #    print("Lich process is complete: {}".format(game_state.lichprocess.poll()))
        #    # if lich exits, exit the game
        #    # TODO: this will be removed if the game process is separated from the game connection
        #    game_state.quit_event.set()

        if not game_state.command_queue.empty():
            # maybe timestamped as its own output stream, so it can be turned off on certain windows
            submitted_command = game_state.command_queue.get()

            # need more utilities here and decide on a permanent prefix

            if submitted_command[0] == ord(b"/"):
                tcp_lines.put(b"pylanthia> " + submitted_command)
                logging.info(submitted_command)

                # currently for reloading highlights, but consider a hot reload mechanism for pylanthia modules, too
                if submitted_command == b"/reload":
                    # need to generalize this, add a method in game_state to reload from itself
                    game_state.highlight_set = set(text_processing.line_config_processor(game_state.highlight_file))
                    game_state.excludes_set = set(text_processing.line_config_processor(game_state.excludes_file))
                    game_state.excludes_regex = [re.compile(text) for text in text_processing.line_config_processor(game_state.excludes_regex_file)]
                    tcp_lines.put(b"[Pylanthia] Highlights & Excludes reloaded.")

                continue # don't send / commands to game server

            # send the command to game 
            gamesock.sendall(submitted_command + b"\n")
            tcp_lines.put(b"> " + submitted_command)
            logging.info(submitted_command)
            game_state.command_history.put(submitted_command)
            game_state.time_last_command = game_state.time

            if submitted_command in [b"exit", b"quit"]:
                game_state.quit_event.set()

            continue  # ensure this whole queue is processed before the rt_command_queue

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
        #
        # 2021/6/14- causes more harm than good
        #if not game_state.rt_command_queue.empty():
        #    current_roundtime = int(game_state.roundtime - game_state.time)
        #    if current_roundtime == 0:
        #        game_state.command_queue.put(game_state.rt_command_queue.get())
