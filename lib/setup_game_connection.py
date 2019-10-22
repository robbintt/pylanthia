'''
'''
import socket
import os
import time
import logging

logging.getLogger(__name__)

# consider merging eaccess here
from lib import eaccess

from config import eaccess_host, eaccess_port, username, password, character, gamestring, server_addr, server_port, frontend_settings, keyfile

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


def _open_game_socket(GAME_KEY=''):
    ''' method is a cleanliness abstraction, relies on parent/enclosed variables
    '''
    if not GAME_KEY:
        GAME_KEY = eaccess.get_game_key(eaccess_host, eaccess_port, username, password, character, gamestring, keyfile)

    gamesock = setup_game_connection(server_addr, server_port, GAME_KEY, frontend_settings)
    return gamesock


def game_connection_controller():
    ''' controller gets its values from this module
    '''
    from config import eaccess_host, eaccess_port, username, password, character, gamestring

    GAME_KEY = ''
    if os.path.isfile(keyfile):
        with open(keyfile) as f:
            GAME_KEY = f.read().encode('utf-8')

    if GAME_KEY:
        try:
            gamesock = _open_game_socket(GAME_KEY)
        # cached game key was expired
        except BrokenPipeError as e:
            logging.debug('Game socket broke on cached GAME_KEY: {}'.format(e))
            gamesock = _open_game_socket()
    # no cached game key
    else:
        gamesock = _open_game_socket()

    return gamesock
