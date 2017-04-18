__author__ = 'VinceVi83'

from Gestion import Interpretation
import socket
import select
CONNECTION_LIST = []  # list of socket clients
RECV_BUFFER = 4096  # Advisable to keep it as an exponent of 2
PORT = 8888

server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# this has no effect, why ?
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_socket.bind(("127.0.0.1", PORT))
server_socket.listen(10)

# Add server socket to the list of readable connections
CONNECTION_LIST.append(server_socket)

send = ''
# Need to fix an IP for the main server
ip_master = '127.0.0.1'

while 1:
    # Get the list sockets which are ready to be read through select
    read_sockets, write_sockets, error_sockets = select.select(CONNECTION_LIST, [], [])

    for sock in read_sockets:
        # New connection
        if sock == server_socket:
            # Handle the case in which there is a new connection recieved through server_socket
            sockfd, addr = server_socket.accept()
            CONNECTION_LIST.append(sockfd)
            ip_cli, port = addr

        else:
            ip_cli, port = addr
            # Data recieved from client, process it
            try:
                data = sock.recv(RECV_BUFFER)
            except:
                print("Client (%s, %s) is offline", addr)
                sock.close()
                CONNECTION_LIST.remove(sock)
                continue
            if ip_cli == ip_master:
                #~ inteprete_cmd need to be define
                returnVal = Interpretation.cmdRPI()
                if returnVal == 1:
                    send = 'done'
                if returnVal == -1:
                    send = 'erreur'
                if returnVal == 0:
                    send = "Command doesn't exist"
            else:
                send = 'You are not my master !!!'
                data = 'fin'.encode()

                sock.send(send.encode())

            if data.decode() == 'fin':
                sock.close()
                CONNECTION_LIST.remove(sock)
                print("Client (%s, %s) is offline", addr)
                continue
server_socket.close()
