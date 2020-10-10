"""
"""
import json
import socket
import os
import subprocess
import time
import logging

logging.getLogger(__name__)

# consider merging eaccess here
from lib import eaccess


def loadconfig(configfile):
    with open(configfile) as f:
        return json.load(f)


def setup_game_connection(server_addr, server_port, key, frontend_settings):
    """ initialize the connection and return the game socket
    """

    gamesock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server = (server_addr, int(server_port))
    gamesock.connect(server)

    time.sleep(
        1
    )  # would be better to get an ACK of some sort before sending the token...
    gamesock.sendall(key)
    gamesock.sendall(b"\n")
    gamesock.sendall(frontend_settings)
    gamesock.sendall(b"\n")

    # needs a second to connect or else it hangs, then you need to send a newline or two...
    time.sleep(1)
    gamesock.sendall(b"\n")
    gamesock.sendall(b"\n")

    return gamesock


def _open_game_socket(jsonconfig, GAME_KEY=""):
    """ method is a cleanliness abstraction, relies on parent/enclosed variables
    """
    if not GAME_KEY:
        GAME_KEY = eaccess.get_game_key(
            jsonconfig["eaccess_host"],
            jsonconfig["eaccess_port"],
            jsonconfig["username"],
            jsonconfig["password"],
            jsonconfig["character"],
            jsonconfig["gamestring"],
        )

    lichprocess = subprocess.Popen(["./lichlauncher.sh"], shell=True)
    time.sleep(1)

    gamesock = setup_game_connection(
        jsonconfig["server_addr"],
        jsonconfig["server_port"],
        GAME_KEY,
        jsonconfig["frontend_settings"].encode("ascii"),
    )

    return gamesock, lichprocess


def game_connection_controller(game_state, character=None):
    """ controller gets its values from this module
    """
    charactersfile = os.getenv("PYLANTHIA_CHARS", "characters.json")
    setupfile = os.getenv("PYLANTHIA_SETUP", "setup.json")
    jsonconfig = loadconfig(setupfile)  # use this config object

    characters = loadconfig(charactersfile)
    character_config = dict()
    # default to character argument, then `env` character
    if not character:
        # must be exact
        character = os.getenv("PYLANTHIA_CHARACTER", None)
    if character:
        for c in characters:
            # allow greedy character abbreviations and case changes
            if c["character"][: len(character)].lower() == character.lower():
                character_config = c
                character = c["character"]  # get matched exact character name
                username = c["username"]  # get matched exact character name

    game_state.character_firstname = character

    jsonconfig.update(character_config)

    # get the cached character key unless the username has reused the key for another character
    # store a dict of cached keys and their associated character
    # if the key is reassigned, we do not wnat to keep it
    # we also want to store all cached keys in 1 file
    # to prevent key reuse we will store per player
    keyfile = eaccess.keyfile_template
    GAME_KEY = ""
    if os.path.isfile(keyfile):
        with open(keyfile) as f:
            try:
                keys_json = json.load(f)
            except json.decoder.JSONDecodeError:
                keys_json = dict() # alternatively skip the rest of the with block

            try:
                # this exists because if you login with a consective character on one
                # account, then the key is reused, so the first and second character
                # logged into will both have the same key, but the second character
                # will always be logged into and the first character would be inaccessible.
                # however, you do receive a new key if you ask for one.
                _last_character, _LAST_GAME_KEY = keys_json[username]
                # only conserve the key on the user if the character is also the same
                if _last_character == character:
                    GAME_KEY = _LAST_GAME_KEY.encode("utf-8")
            # no game key for this username
            except KeyError:
                pass

    if GAME_KEY:
        try:
            gamesock, lichprocess = _open_game_socket(jsonconfig, GAME_KEY)
        # cached game key was expired
        except BrokenPipeError as e:
            logging.debug("Game socket broke on cached GAME_KEY: {}".format(e))
            gamesock, lichprocess = _open_game_socket(jsonconfig)
    # no cached game key
    else:
        gamesock, lichprocess = _open_game_socket(jsonconfig)

    return gamesock, lichprocess
