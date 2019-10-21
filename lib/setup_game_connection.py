'''
'''
import socket
import time

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
