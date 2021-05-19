# -*- coding: utf-8 -*-

import argparse
from socket import *
from datetime import datetime
import time
import re
import threading
import os
import sys
"""!!!!!!!!!"""
os.chdir(os.getcwd())
"""!!!!!!!!!"""

parser = argparse.ArgumentParser(description='TCP/UDP client')

parser.add_argument('serverIP', type=str, nargs='?', default='127.0.0.1', help='server address (default: local host)')
parser.add_argument('serverPort', type=int, nargs='?', default=3331, help='server port (default: 3331)')
parser.add_argument('clientUDPPort', type=int, nargs='?', default=10000, help='UDP port client listening to (default: 3331)')

args = parser.parse_args()

UDPServerExitFlag = False


class TCPClient:
    def __init__(self, serverName, serverPort, UDPPort, threadingQueue):
        self.serverName = serverName
        self.serverPort = serverPort
        self.UDPPort = UDPPort
        self.userName = ''
        self.exitFlag = False
        self.queueLock = threadingQueue
        self.threadID = 1
        self.logInTime = datetime.now()
        self.UDPServerLock = threading.Condition()
        self.UDPSenderLock = threading.Condition()

    def run(self):
        # initiate TCP client
        clientSocket = socket(AF_INET, SOCK_STREAM)
        clientSocket.settimeout(1)  # longest waiting time is 1 s
        clientSocket.connect((self.serverName, self.serverPort))
        clientSocket.send("Hello".encode())

        while not self.exitFlag:
            if self.userName == '':
                self.logCheck(clientSocket)
            UserCommands = input("Enter one of the following commands (MSG, DLT, EDT, RDM, ATU, OUT, UPD): ")
            # this is the main socket
            self.agentRun(clientSocket, UserCommands)
            time.sleep(0.1)
        # socket shut down
        clientSocket.close()

    def agentRun(self, client_socket, User_commands):
        global UDPServerExitFlag
        try:
            if User_commands[0:3] == "OUT":
                if len(User_commands.split()) > 1:
                    print("Error. Invalid command!")
                else:
                    client_socket.send("OUT".encode())
                    print(f"\033[1;32mGoodBye {self.userName}!\033[0m")
                    self.exitFlag = True
                    UDPServerExitFlag = True
            elif User_commands[0:3] == 'MSG':
                # print("User_commands: ", User_commands)
                if len(User_commands.split()) < 2:
                    print("Error. Invalid command!")
                else:
                    try:
                        client_socket.send(User_commands.encode())
                        feedback = client_socket.recv(1024)
                        print("".join(feedback.decode()))
                    except:
                        self.abnormalInterrupt()

            elif User_commands[0:3] == 'DLT':
                if not self.DLTCheck(User_commands):
                    print("Error. Invalid command!")
                else:
                    try:
                        client_socket.send((User_commands + ' ' + self.userName).encode())
                        feedback = client_socket.recv(1024)
                        print("".join(feedback.decode()))
                    except:
                        self.abnormalInterrupt()

            elif User_commands[0:3] == 'EDT':
                if not self.EDTCheck(User_commands):
                    print("Error. Invalid command!")
                else:
                    try:
                        client_socket.send((User_commands + ' ' + self.userName).encode())
                        feedback = client_socket.recv(1024)
                        print("".join(feedback.decode()))
                    except:
                        self.abnormalInterrupt()

            elif User_commands[0:3] == 'RDM':
                if not self.RDMCheck(User_commands):
                    print("Error. Invalid command!")
                else:
                    try:
                        client_socket.send(User_commands.encode())
                        feedback = client_socket.recv(1024).decode()
                        count = 0
                        while feedback != 'no new message':
                            client_socket.send('Continue'.encode())
                            print("".join(feedback))
                            count += 1
                            feedback = client_socket.recv(1024).decode()
                        if not count:
                            print("".join(feedback))
                    except:
                        self.abnormalInterrupt()
                        return

            elif User_commands[0:3] == 'ATU':
                if len(User_commands) > 3:
                    print("Error. Invalid command!")
                else:
                    self.ATU(client_socket, User_commands)

            elif User_commands[0:3] == 'UPD':
                userCommands = User_commands.split()
                if len(userCommands) < 3:
                    print("Error. Invalid command!")
                else:
                    self.UDP(*userCommands[1:], client_socket)
            else:
                print("Error. Invalid command!")
        except IndexError:
            print("Error. Invalid command!")

    def logCheck(self, client_socket):
        UserName = ''
        loginFlag = False
        while not loginFlag:
            try:
                logInMessage = client_socket.recv(1024).decode()
                # if server ask to log in
                while logInMessage == 'LogIn':
                    try:
                        UserName = input("\033[1;32mUserName\033[0m: ")
                        PassWord = input("\033[1;32mPassword\033[0m: ")
                        client_socket.send(f"LogIn {UserName} {PassWord} {self.UDPPort}".encode('utf-8'))
                        feedback = client_socket.recv(1024)
                    except:
                        continue
                    if feedback.decode() == 'Welcome':
                        loginFlag = 1
                        logInMessage = 'Welcome'
                        print(f"Welcome to TOOM! (the client should upload the UDP port number {self.UDPPort}, "
                              "i.e. the second argument, to the server in the background after a user is log in).")

                    elif feedback.decode() == 'AttemptsOut':
                        print("Your account is blocked due to multiple login failures. Please try again later")

                    elif feedback.decode() == 'ReLog':
                        print("User already online, please try again later")

                    else:
                        print("Invalid Password. Please try again")
                self.userName = UserName
                self.logInTime = datetime.now()
                # start UDP server
                UDP_server = UDPServer(self.threadID, self.userName, self.UDPPort, self.UDPServerLock)
                UDP_server.start()
            except:
                self.abnormalInterrupt()
                break

    def abnormalInterrupt(self):
        """
            when abnormal interrupt happened,
            retrieve this function to close TCP client
        """
        global UDPServerExitFlag
        print("\033[1;31mWarning:\033[0m Server disconnected, please try to reconnect later !")
        self.exitFlag = True
        UDPServerExitFlag = True


    @staticmethod
    def DLTCheck(user_commands):
        DLTCommands = user_commands.split()
        if len(DLTCommands) < 6:
            return False
        try:
            if re.match("#\d+", DLTCommands[1]) is None:
                return False
            if re.match("\d+", DLTCommands[2]) is None:
                return False
            if re.match("[a-zA-Z]+", DLTCommands[3]) is None:
                return False
            if re.match("\d+", DLTCommands[4]) is None:
                return False
            if re.match("\d+:\d+:\d+", DLTCommands[5]) is None:
                return False
        except IndexError:
            return False
        return True

    @staticmethod
    def EDTCheck(user_commands):
        EDTCommands = user_commands.split()
        if len(EDTCommands) < 7:
            return False
        try:
            if re.match("#\d+", EDTCommands[1]) is None:
                return False
            if re.match("\d+", EDTCommands[2]) is None:
                return False
            if re.match("[a-zA-Z]+", EDTCommands[3]) is None:
                return False
            if re.match("\d+", EDTCommands[4]) is None:
                return False
            if re.match("\d+:\d+:\d+", EDTCommands[5]) is None:
                return False
        except IndexError:
            return False
        return True

    @staticmethod
    def RDMCheck(user_commands):
        RDMCommands = user_commands.split()
        if len(RDMCommands) < 5:
            return False
        try:
            messageTimeStamp = " ".join(t for t in RDMCommands[1:5])
            try:
                datetime.strptime(messageTimeStamp, '%d %b %Y %H:%M:%S')
            except ValueError:
                return False
        except IndexError:
            return False
        return True

    def ATU(self, client_socket, User_commands, printFlag=True):
        try:
            client_socket.send(User_commands.encode())
            feedback = client_socket.recv(1024)
            if feedback[:20].decode() == 'no other active user':
                print('no other active user')
                return
            with self.queueLock:
                if os.path.exists("cse_userlog.txt"):
                    os.remove("cse_userlog.txt")
                with open("cse_userlog.txt", 'a+') as f:
                    while True:
                        f.write(feedback.decode())
                        try:
                            feedback = client_socket.recv(1024)
                        except timeout:
                            break
                        except:
                            self.abnormalInterrupt()
                if printFlag:
                    with open("cse_userlog.txt", 'r') as f:
                        print("".join(s for s in f.readlines()))
                self.queueLock.notify()
        except:
            self.abnormalInterrupt()

    def UDP(self, receiverName, videoName, client_socket):
        # get the ATU file
        self.ATU(client_socket, "ATU", False)
        with self.queueLock:
            with open("cse_userlog.txt", 'r') as f:
                userLogs = f.readlines()
            for userInfo in userLogs:
                userInfoList = userInfo.split(';')
                if userInfoList[2].lstrip(' ') == receiverName:
                    sender = UDPSender(self.threadID + 1, self.userName, (userInfoList[3].lstrip(' '),
                                                                       int(userInfoList[4].lstrip(' ').rstrip('\n'))),
                                       videoName, self.UDPServerLock)
                    sender.start()
                    self.threadID += 1
                    break
            self.queueLock.notify()


class UDPServer(threading.Thread):
    def __init__(self, threadID, clientName, listenUDPPort, queueLock):
        super(UDPServer, self).__init__(daemon=True)
        self.threadID = threadID
        self.clientName = clientName
        self.listenUDPPort = listenUDPPort
        self.queueLock = queueLock

    def run(self):
        global UDPServerExitFlag
        # initiate UDP server socket
        serverSocket = socket(AF_INET, SOCK_DGRAM)
        serverSocket.bind((gethostbyname(gethostname()), self.listenUDPPort))  # automatically bind a possible port
        serverSocket.settimeout(1)
        while not UDPServerExitFlag:
            try:
                message, clientAddress = serverSocket.recvfrom(1024)
            except timeout:
                continue
            # new UDP client want to begin transmission
            if message[:7].decode() == "VideoIn":
                senderName, videoName = message[8:].decode().split('_')
                video, clientAddress = serverSocket.recvfrom(1024)
                localVideoName = self.clientName + '_' + videoName
                with self.queueLock:
                    with open(localVideoName, 'wb+'):
                        pass
                    with open(localVideoName, 'ab') as v:
                        while True:
                            v.write(video)
                            try:
                                video, clientAddress = serverSocket.recvfrom(1024)
                            except timeout:
                                break
                    self.queueLock.notify()
                    print(f"\nReceived {videoName} from {senderName}")
        serverSocket.close()


class UDPSender(threading.Thread):
    def __init__(self, threadID, clientName, clientAddress, videoName, queueLock):
        super(UDPSender, self).__init__(daemon=True)
        self.threadID = threadID
        self.clientAddress = clientAddress
        self.clientName = clientName
        self.queueLock = queueLock
        self.videoName = clientName + '_' + videoName

    def run(self):
        sendSocket = socket(AF_INET, SOCK_DGRAM)
        sendSocket.settimeout(3)
        with self.queueLock:
            with open(self.videoName, 'rb') as v:
                sendSocket.sendto(f"VideoIn {self.videoName}".encode(), self.clientAddress)
                time.sleep(0.01)
                videoSlice = v.read(1024)
                while videoSlice:
                    # short time stop to wait for reading finished
                    time.sleep(0.001)
                    sendSocket.sendto(videoSlice, self.clientAddress)
                    videoSlice = v.read(1024)
            self.queueLock.notify()
            print(f"\n{self.videoName} has been uploaded")
        sendSocket.close()


if __name__ == '__main__':
    if re.match("\d+.\d+.\d+.\d+", args.serverIP) is None:
        print("Invalid server IP address")
        sys.exit(1)
    mainClient = TCPClient(args.serverIP, args.serverPort, args.clientUDPPort, threading.Condition())
    mainClient.run()

