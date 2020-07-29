"""
"""
import time


def gametime_incrementer(game_state, MAX_IDLE_TIME=60 * 60 * 2):
    """

    move max idle time to config
    """
    while True:
        time.sleep(1)

        # this is incremented since we only get gametime about every 5-20 seconds
        game_state.time += 1

        # this should only run the first time global game state is set
        # otherwise (as it is now) we check this way more than necessary...
        # funky hack to make sure we aren't incrementing from zero still
        # it's acceptable to use a known global game time since it increments forever but still sloppy
        if game_state.time > 100000 and game_state.time_last_command == 0:
            game_state.time_last_command = game_state.time

        # quit if idle too long
        time_since_last_command = game_state.time - game_state.time_last_command
        if time_since_last_command >= MAX_IDLE_TIME:
            game_state.command_queue.put(b"quit")
