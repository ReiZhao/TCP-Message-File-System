# -*- coding: utf-8 -*-
from socket import *
import threading
import os
import time
from datetime import datetime
import argparse
from collections import defaultdict

""" Server to client Commands
    --> LogIn:  prompt to log in
    --> Welcome:  Successful Log in
    --> Invalid: Receive invalid command or incorrect log in
"""

""" Client to Server Commands
    --> LogIn UserName Password:    Request to log in
    --> ConnectClose:   Shut down connection
    
"""

# default serverPort = 3331
# default allowed failed attempts == 5
parser = argparse.ArgumentParser(description='Server')
parser.add_argument('port', type=int, nargs='?', default=3331, help='port (default: 3331)')
parser.add_argument('failedAttempts', type=int, nargs='?', default=5, help='Allowed failed log in attempts for each client, must in [1, 5]')
parser.add_argument('afterFailWaitTime', type=int, nargs='?', default=10, help='Waiting time after the largest failed log in attempts for each client')
parser.add_argument('maxListen', type=int, nargs='?', default=10,
                    help='Max clients listened by this server (default: 10)')

args = parser.parse_args()
if args.port < 1024 or args.port == 8080:
    print("Invalid server port")
    raise KeyError
if args.failedAttempts < 1 or args.failedAttempts > 5:
    print("Invalid failedAttempts, must in [1, 5]")
    raise KeyError

print("\033[1;31mNotice:\033[0m default maximum supported clients = 10")

ServerUpdateTime = 0.005
messageNumber = 1
authorisedClients = defaultdict(list)
messageLogAddress = 'messagelog.txt'
failedAttempts = args.failedAttempts
afterFailWaitTime = args.afterFailWaitTime
isServerOpen = True
connectionMaintainTime = 600


class ServerThread (threading.Thread):
    """
        communication Thread: Hold TCP connection with specific client
    """
    def __init__(self, threadID, address, queueLock, client):
        threading.Thread.__init__(self, daemon=True)
        self.threadID = threadID
        self.threadAddress = address
        self.queueLock = queueLock
        self.client = client
        self.clientName = ''
        self.attempt = [0, 0, False]  # [attemptTimes, lastAttemptTime, filedFlag]

        self.connectionTime = datetime.now()
        self.isOpen = True
        self.logIn = False

    def run(self):
        self.process_data()

    """Main function"""
    def process_data(self):
        # check if client has logged in
        while not self.logIn:
            self.authentication()

        while self.logIn and self.isOpen:
            # when successfully receive a message, acquire for threading lock
            request = self.client.recv(1024)
            if not request:
                with self.queueLock:
                    self.OUT()
                    self.queueLock.notify()
                break
            with self.queueLock:
                # get client commands
                commands = request.decode().split()

                if len(commands) and commands[0] == "OUT":
                    self.OUT()

                elif len(commands) and commands[0] == "MSG":
                    message = " ".join(word for word in commands[1:])
                    self.MSG(message)

                elif len(commands) and commands[0] == "DLT":
                    self.DLT(*commands[1:])

                elif len(commands) and commands[0] == "EDT":
                    self.EDT(*commands[1:])

                elif len(commands) and commands[0] == "RDM":
                    self.RDM(*commands[1:])

                elif len(commands) and commands[0] == "ATU":
                    self.ATU()

                self.queueLock.notify()
            time.sleep(ServerUpdateTime)
        self.client.close()
        print(f"\033[1;32mEvent:\033[0m Connect between client\033[1;32m {self.clientName}\033[0m {self.threadAddress} "
              f"log out at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    def authentication(self):
        """
        Check if accept current client to be connected
        """
        global authorisedClients
        global failedAttempts
        global afterFailWaitTIme

        """LogIN UserName Password"""
        receivedMsg = self.client.recv(1024).decode().split()
        if not len(receivedMsg):
            return
        if receivedMsg[0] != 'LogIn':
            self.client.send('LogIn'.encode())
            return
        try:
            self.clientName, password, UDPPort = receivedMsg[1], receivedMsg[2], receivedMsg[3]
            key = self.clientName
        except IndexError:  # connection unexpected broken, shut down service
            self.isOpen = False
            return
        with self.queueLock:
            # error username
            if key not in authorisedClients:
                self.client.send('Invalid'.encode())
            # correct user name
            else:
                # repeated log in
                if authorisedClients[key][-1]:
                    self.client.send('ReLog'.encode())

                # error password
                elif authorisedClients[key][0] != password:
                    # if not failed yet
                    if not authorisedClients[key][3] and authorisedClients[key][1] < failedAttempts:
                        self.client.send('Invalid'.encode())
                        authorisedClients[key][1] += 1
                        authorisedClients[key][2] = datetime.now()
                    elif not authorisedClients[key][3] and authorisedClients[key][1] >= failedAttempts:
                        self.client.send('AttemptsOut'.encode())
                        authorisedClients[key][1] = 0
                        authorisedClients[key][2] = datetime.now()
                        authorisedClients[key][3] = True
                    else:  # if failed
                        visitedTime = datetime.now()
                        # protection model, interval <= 10s (afterFailWaitTIme)
                        if (visitedTime - authorisedClients[key][2]).seconds <= afterFailWaitTime:
                            self.client.send('AttemptsOut'.encode())
                        # protection model, interval > 10s, reset
                        else:
                            self.client.send('Invalid'.encode())
                            authorisedClients[key][1] += 1
                            authorisedClients[key][2] = visitedTime
                            authorisedClients[key][3] = False
                    # correct password
                else:
                    # valid log in, but still in protection model
                    visitedTime = datetime.now()
                    if authorisedClients[key][3] and (visitedTime - authorisedClients[key][2]).seconds <= afterFailWaitTime:
                        self.client.send('AttemptsOut'.encode())
                    else:
                        # valid log in, working model, build connection immediately
                        self.logIn = True
                        # change public recording list, acquire for threading lock
                        authorisedClients[key] = [password, 0, datetime.now(), False, (self.threadAddress[0], UDPPort), True]
                        self.client.send("Welcome".encode())
                    connectedTime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    self.connectionTime = connectedTime
                    print(f"\033[1;32mEvent:\033[0m Client {receivedMsg[1]} {self.threadAddress} log in at {connectedTime}")
            self.queueLock.notify()

    def MSG(self, message):
        global messageNumber
        global messageLogAddress
        with open(messageLogAddress, 'a') as messageLog:
            timeStamp = datetime.now().strftime('%d %b %Y %H:%M:%S')
            print(f"\033[1;32m{'== ' * 20}\033[0m")
            feedbackMessage = f" Message #{messageNumber} posted at {timeStamp}."
            self.client.send(feedbackMessage.encode())
            messageLog.write(f"{messageNumber}; {timeStamp}; {self.clientName}; {message}; no\n")
        print(f"{self.clientName} posted MSG #{messageNumber} \"{message}\" at {timeStamp}.")
        messageNumber += 1

    def DLT(self, *args):
        timeStamp = datetime.now().strftime('%d %b %Y %H:%M:%S')
        global messageNumber
        messageID = args[0][1:]
        messageTimeStamp = " ".join(t for t in args[1:5])
        userName = args[5]
        findFlag = False
        # status: indications of finding result
        # status = [fileEmpty, lineIDMatched, lineTimeStampMatched, LineUserMatched]
        status = [True] + [False] * 3
        with open('messagelog.txt', 'r') as old_file:
            with open('messagelog.txt', 'r+') as new_file:
                # locate the target delete line
                while True:
                    try:
                        cursorPosition = old_file.tell()
                        current_lineID, current_lineTimeStamp, current_lineUser, deleteContents = old_file.readline().split(
                            ';')[:4]
                    except ValueError:
                        break

                    status = [False, current_lineID == messageID,
                              current_lineTimeStamp.lstrip(' ') == messageTimeStamp,
                              current_lineUser.lstrip(' ') == userName
                              ]
                    messageNumber = int(current_lineID)
                    if status == [False] + [True] * 3:
                        findFlag = True
                        break
                # file empty
                if status[0]:
                    feedbackMessage = 'Message log is empty.'
                    self.client.send(feedbackMessage.encode())
                    print(f"\033[1;32m{'== ' * 20}\033[0m")
                    print(f"{self.clientName} attempts to delete MSG #{messageID} at {timeStamp}. "
                          f"But the message log is empty. ")
                # all match
                elif not status[0] and findFlag:
                    # oldFile cursor move to next line
                    next_line = old_file.readline()
                    new_file.seek(cursorPosition, 0)
                    # cover contents in the new file
                    while next_line:
                        next_line_list = next_line.split(';')
                        next_line_list[0] = f"{int(next_line[0]) - 1}"
                        messageNumber = int(next_line[0])
                        print(messageNumber)
                        next_line = ';'.join(s for s in next_line_list)
                        new_file.write(next_line)
                        next_line = old_file.readline()
                    # cut off new file as one line has been deleted
                    new_file.truncate()
                    deleteTime = datetime.now().strftime('%d %b %Y %H:%M:%S')
                    print(f"\033[1;32m{'== ' * 20}\033[0m")
                    feedbackMessage = f"Message #{messageID} deleted at {deleteTime}."
                    self.client.send(feedbackMessage.encode())
                    print(f"{self.clientName} deleted MSG #{messageID} \"{deleteContents}\" at {deleteTime}.")
                else:
                    feedbackMessage = f"Unauthorised to delete Message #{messageID}."
                    self.client.send(feedbackMessage.encode())
                    print(f"\033[1;32m{'== ' * 20}\033[0m")
                    print(f"{self.clientName} attempts to delete MSG #{messageID} at {timeStamp}. "
                          f"Authorisation fails. ")

    def EDT(self, *args):
        timeStamp = datetime.now().strftime('%d %b %Y %H:%M:%S')
        messageID = args[0][1:]
        messageTimeStamp = " ".join(t for t in args[1:5])
        newMessage = " ".join(t for t in args[5:-1])
        userName = args[-1]
        findFlag = False
        fileNotEmptyFlag = True
        with open('messagelog.txt', 'r') as old_file:
            with open('messagelog.txt', 'r+') as new_file:
                cursorPosition = old_file.tell()
                try:
                    current_lineID, current_lineTimeStamp, current_lineUser, deleteContents = old_file.readline().split(
                        ';')[:4]
                except ValueError:
                    fileNotEmptyFlag = False
                # locate the target delete line
                while fileNotEmptyFlag:
                    if (current_lineID, current_lineTimeStamp.lstrip(' '), current_lineUser.lstrip(' ')) == (
                            messageID, messageTimeStamp, userName):
                        findFlag = True
                        break
                    try:
                        cursorPosition = old_file.tell()
                        current_lineID, current_lineTimeStamp, current_lineUser, deleteContents = old_file.readline().split(
                            ';')[:4]
                    except ValueError:
                        break
                # message log empty
                if not fileNotEmptyFlag:
                    feedbackMessage = 'Message log is empty.'
                    self.client.send(feedbackMessage.encode())
                    print(f"\033[1;32m{'== ' * 20}\033[0m")
                    print(f"{self.clientName} attempts to delete MSG #{messageID} at {timeStamp}. "
                          f"But the message log is empty. ")
                # find target line
                elif findFlag and fileNotEmptyFlag:
                    # oldFile cursor move to next line
                    next_line = old_file.readline()
                    new_file.seek(cursorPosition, 0)
                    edtTime = datetime.now().strftime('%d %b %Y %H:%M:%S')
                    new_line = f"{current_lineID}; {edtTime};{current_lineUser}; {newMessage}; yes\n"
                    new_file.write(new_line)
                    # cover contents in the new file
                    while next_line:
                        new_file.write(next_line)
                        next_line = old_file.readline()
                    # cut off new file as one line has been changed
                    new_file.truncate()
                    print(f"\033[1;32m{'== ' * 20}\033[0m")
                    feedbackMessage = f"Message #{messageID} edited at {edtTime}."
                    self.client.send(feedbackMessage.encode())
                    print(f"{self.clientName} edited MSG #{messageID} \"{newMessage}\" at {edtTime}.")
                # target line cannot match the info from client
                else:
                    feedbackMessage = f"Unauthorised to edited Message #{messageID}."
                    self.client.send(feedbackMessage.encode())
                    print(f"\033[1;32m{'== ' * 20}\033[0m")
                    print(f"{self.clientName} attempts to edited MSG #{messageID} at {timeStamp}. "
                          f"Authorisation fails. ")

    def RDM(self, *args):
        messageTimeStamp = " ".join(t for t in args)
        messagedt = datetime.strptime(messageTimeStamp, '%d %b %Y %H:%M:%S')
        with open('messagelog.txt', 'r') as f:
            current_line = f.readline()
            print(f"\033[1;32m{'== ' * 20}\033[0m")
            print(f"{self.clientName} issued RDM command\nReturn Messages:")
            while current_line and current_line != '\n':
                current_line_list = current_line.split(';')
                current_line_timeStamp = current_line_list[1].lstrip(' ')
                current_line_dt = datetime.strptime(current_line_timeStamp, '%d %b %Y %H:%M:%S')
                # send found line to client
                if current_line_dt >= messagedt:
                    if current_line_list[-1] == ' no\n':
                        feedbackMessage = f"#{current_line_list[0]}{current_line_list[2]},{current_line_list[3]}, posted at{current_line_list[1]}"
                        self.client.send(feedbackMessage.encode())
                        self.client.recv(1024)
                    else:
                        feedbackMessage = f"#{current_line_list[0]}{current_line_list[2]},{current_line_list[3]}, edited at{current_line_list[1]}"
                        self.client.send(feedbackMessage.rstrip('\n').encode())
                        self.client.recv(1024)
                    print(feedbackMessage)
                current_line = f.readline()
        self.client.send("no new message".encode())
        print(f"=---=---=---=---=---=---=---=---=---=---=\nNo more new message after {messageTimeStamp}")

    def ATU(self):
        global authorisedClients
        findFlag = False
        print(f"\033[1;32m{'== ' * 20}\033[0m")
        print(f"{self.clientName} issued ATU command.")
        with self.queueLock:
            keys = list(authorisedClients.keys())
            with open('cse_userlog.txt', 'w+') as f:
                index = 1
                for key in keys:
                    if authorisedClients[key][-1] and key != self.clientName:
                        findFlag = True
                        f.write(f"{index}; {authorisedClients[key][2].strftime('%Y-%m-%d %H:%M:%S')}; {key}; {authorisedClients[key][-2][0]}; {authorisedClients[key][-2][1]}\n")
                        print()
                        index += 1

            if not findFlag:
                print("No other active user")
                self.client.send("no other active user".encode())
            else:
                print("Return active user list:")
                with open('cse_userlog.txt', 'r') as f:
                    usr_log = f.readline()
                    while usr_log and usr_log != '\n':
                        self.client.send(usr_log.encode())
                        _, timeStamp, userName, IP, port = usr_log.split(';')
                        port = port.rstrip('\n')
                        print(f"{userName};{IP};{port}; active since{timeStamp}.")
                        usr_log = f.readline()

    def OUT(self):
        self.isOpen = False
        try:
            authorisedClients[self.clientName][-1] = False
            authorisedClients[self.clientName][-2] = ()
        except IndexError:
            pass


class Server(threading.Thread):
    """
        Thread: listening socket
    """
    def __init__(self, serverPort, queueLock):
        super(Server, self).__init__(daemon=True)
        self.serverPort = serverPort
        self.queueLock = queueLock
        self.readCredentials()
        self.readMessageLog()

    def run(self):
        """
        Main Loop, listening socket running here
        initiating new server-client thread when new clients log in
        """
        global isServerOpen
        threadID = 1
        serverListeningSocket = socket(AF_INET, SOCK_STREAM)
        # enable reuse IP address to bind others sockets
        serverListeningSocket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        serverListeningSocket.bind((gethostbyname(gethostname()), self.serverPort))
        serverListeningSocket.listen(args.maxListen)
        print(f"\n\033[1;32m           ==*** Welcome! ***==      \033[0m \n"
              f"Server running on {gethostbyname(serverListeningSocket.getsockname()[0])}, "
              f"Server Port: {self.serverPort}\n"
              f"\033[1;32m==*** Waiting for the first connection ***==\033[0m\n")
        while isServerOpen:
            client, address = serverListeningSocket.accept()

            connectedTime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print(f"\033[1;32mEvent:\033[0m Client {address} are trying to log in at {connectedTime}")
            newThread = ServerThread(threadID, address, self.queueLock, client)
            newThread.start()
            threadID += 1

    @staticmethod
    def readCredentials():
        global authorisedClients
        """Load clients authentication from credentials.txt """
        # if not os.path.exists('credentials.txt'):
        #     raise FileNotFoundError
        with open('credentials.txt', 'r') as f:
            for clientInfo in f.readlines():
                try:
                    clientName, password = clientInfo.split()
                    """password, attemptTimes, addRecording time, failedLogFlag, address, ConnectedFlag"""
                    # key ClientName
                    authorisedClients[clientName] = [password, 0, 0, False, (), False]
                except ValueError:
                    print(f"\033[1;31mWarning:\033[0m one of client authentication recording is not valid, "
                          f"system has skipped it. Invalid recording is \033[1;31m{clientInfo}\033[0m.")

    @staticmethod
    def readMessageLog():
        global messageNumber
        # if not os.path.exists('messagelog.txt'):
        #     raise FileNotFoundError
        # read the last messageID in messagelog.txt
        if not os.path.exists('messagelog.txt'):
            with open('messagelog.txt', 'w+') as f:
                pass
        else:
            with open("messagelog.txt", 'r') as f:
                f.seek(0)
                fileContent = f.readlines()
                if len(fileContent) and fileContent[-1] != '\n':
                    messageNumber = int(fileContent[-1].split(';')[0]) + 1


if __name__ == '__main__':
    myServer = Server(args.port, threading.Condition())
    myServer.start()
    while True:
        administratorCommand = input("To stop services, input\033[1;32m shut down\033[0m\n")
        if administratorCommand == 'shut down':
            isServerOpen = False
            break
    print(f"\033[1;32mServer shut down at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\033[0m")
