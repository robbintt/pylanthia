''' Get a token from a login and password

EAccess Protocol: http://warlockclient.wikia.com/wiki/EAccess_Protocol

SGE Protocol: https://gswiki.play.net/SGE_protocol/saved_posts
'''
import socket
import time

from config import eaccess_host, eaccess_port, username, password, character, gamestring

def get_game_key(host, port, username, password):

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server = (host, int(port))
    sock.connect(server)

    time.sleep(1) # would be better to get an ACK of some sort before sending the token...

    sock.sendall(b'K\n') # request a key

    tcp_buffer = bytes()
    while b'\n' not in tcp_buffer:
        tcp_buffer += sock.recv(64)

    pw_hashing_key, _sep, _tail = tcp_buffer.partition(b'\n')

    # used to test out the xor results, zip is a nice code pattern for making the bytearray later
    #_pass_ints = [l for l in password]
    #_key_ints = [l for l in pw_hashing_key]
    #_xor_ints = [p ^ k for p, k in zip(_pass_ints, _key_ints)]

    hashed_password = list()
    for i, letter in enumerate(password):
        # bytes yield an int if you index them, needs python 3
        # these bytes are in range 0-255, they are true bytes, not ascii standard (0-127)
        # algo from warneck; warneck's 2 sources are:
        # 1. https://www.reddit.com/r/dragonrealms/comments/4xhcb5/stepbystep_guide_on_connecting_to_dr_via_blowtorch/
        # 2. https://github.com/jrhz/tf-dr/blob/master/DRlogin
        xor_letter = pw_hashing_key[i] ^ letter
        if pw_hashing_key[i] >= ord('a'): # 'a' is 97
            xor_letter = xor_letter ^ 64 # 64 == 0x40
        if xor_letter < ord(' '): # ' ' space is 32
            xor_letter = xor_letter | 128 # 128 == 0x80
        hashed_password.append(xor_letter)
        #hashed_password.append((pw_hashing_key[i] ^ (password[i] - 32)) + 32)
    
    # really hashed_password should already be convertible to bytes() because it is a seq of ints
    # consider moving all this processing to a bytearray for simplicity
    hashed_password = bytes(hashed_password)

    def get_login_key(username, hashed_password):
    
        # get a login key
        sock.sendall(b'A\t' + username + b'\t' + hashed_password + b'\n') # request a key
        tcp_buffer = bytes()
        while b'\n' not in tcp_buffer:
            tcp_buffer += sock.recv(64)

        response, _sep, _tail = tcp_buffer.partition(b'\n')

        response_parts = response.split(b'\t')
        print(response_parts, len(response_parts))

        return response_parts


    # doesn't work, need to restart the whole eaccess connection
    tries = 1
    while tries > 0:
        response_parts = get_login_key(username, hashed_password)
        if len(response_parts) == 5:
            break
        else:
            tries -= 1
            time.sleep(5)
    else:
        raise(Exception("Login key attempt failed 3 times!"))


    if response_parts[0] != b'A':
        print('Not well formed!:', response_parts)
        pass # this should probably throw an Exception

    KEY = response_parts[3] # here ya go
    print(type(KEY))

    # choose game (could specify DR, DRF, DRT, DRX? - check), not sure if necessary
    sock.sendall(b'G\t' + gamestring + b'\n')
    # drop the response for now, we specify this in settings
    tcp_buffer = bytes()
    while b'\n' not in tcp_buffer:
        tcp_buffer += sock.recv(64)
    print(tcp_buffer)

    # give character names, if you want it for validation
    sock.sendall(b'C\n')
    # drop the response for now, we specify this in settings
    tcp_buffer = bytes()
    while b'\n' not in tcp_buffer:
        tcp_buffer += sock.recv(64)
    print(tcp_buffer)

    response, _sep, _tail = tcp_buffer.partition(b'\n')

    print(b'get character key from this response: ' + response)

    response_parts = response.split(b'\t')[5:] # trim the leading stuff

    character_keys = { char.upper(): key for char, key in zip(response_parts[1::2], response_parts[::2]) }
    character_upper = character.upper() # compare apples to apples

    if character_upper not in character_keys.keys():
        raise Exception("Your character name is not on this account")

    # choose character - not sure if necessary, can use for validation
    sock.sendall(b'L\t' + character_keys[character_upper] + b'\tPLAY\n')
    # drop the response for now, we specify this in settings
    tcp_buffer = bytes()
    while b'\n' not in tcp_buffer:
        tcp_buffer += sock.recv(64)
    print("ready to play: ", tcp_buffer)

    # character key is now attached to the game key
    return KEY


if __name__ == '__main__':
    ''' Get a token for the game

    ACCOUNT, GAME, CHARACTER - these must all be provided... probably just in config
    '''
    game_key = get_game_key(eaccess_host, eaccess_port, username, password)

    print(game_key)


