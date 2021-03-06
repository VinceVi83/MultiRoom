from tkinter import *

import tkinter as tk
from tkinter import font  as tkfont
import socket
import subprocess
import netifaces as ni
from threading import *
from tkinter import filedialog

# Todo remove it..
def getVarEnvironnement(var):
  return subprocess.check_output("echo $" + var, shell=True).decode().strip()

interface = getVarEnvironnement("interface")
port = 8888


class GUI(tk.Tk):

    def __init__(self, *args, **kwargs):
        tk.Tk.__init__(self, *args, **kwargs)
        self.thread1 = None
        self.stop_threads = Event()
        self.login = ""
        self.title_font = tkfont.Font(family='Helvetica', size=18, weight="bold", slant="italic")
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        container = tk.Frame(self)
        container.pack(side="top", fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.frames = {}
        for F in (ConnectFrame, VLController):
            page_name = F.__name__
            frame = F(parent=container, controller=self)
            self.frames[page_name] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.changeFrame("ConnectFrame")

    def receive(self):
        while not self.stop_threads.is_set():
            try:
                text = self.client.recv(1024).decode()
                if "metadata" in text:
                    infos = text.split("metadata:")[1].split("\n1\n")
                    self.frames["VLController"].updateInfos(infos)
                else:
                    if text:
                        print("From Server : " + text)
            except:
                print("Problem exception")
                break

    def startReceiver(self):
        self.stop_threads.clear()
        self.thread1 = Thread(target = self.receive)
        self.thread1.start()

    def stopReceiver(self):
        self.client.close()
        self.stop_threads.set()
        self.thread1.join()
        self.thread1 = None

    def changeFrame(self, page_name):
        '''Show a frame for the given page name'''
        frame = self.frames[page_name]
        frame.tkraise()

    def disconnect(self):
        msg = self.login + "end"

        self.client.send(msg.encode())
        self.stopReceiver()
        self.changeFrame("ConnectFrame")

    def stopServices(self):
        msg = self.login + "endstop"
        try:
            self.client.send(msg.encode())
        except:
            print("Ok")
        self.stopReceiver()
        self.changeFrame("ConnectFrame")


class ConnectFrame(tk.Frame):

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.controller = controller
        self.labelTitle = Label(self, text="Connexion", font=controller.title_font)
        self.labelTitle.pack()

        # Création de nos widgets
        self.frameConnect = Frame(self, width=768, height=576, borderwidth=1)
        self.frameConnect.pack(fill=BOTH)


        self.labelLogin = Label(self.frameConnect, text="Login")
        self.labelPWD = Label(self.frameConnect, text="Password")
        self.labelIP = Label(self.frameConnect, text="IP")

        self.entryLogin = Entry(self.frameConnect)
        self.entryPWD = Entry(self.frameConnect)
        self.entryIP = Entry(self.frameConnect)
        self.entryIP.insert(0, "192.168.0.29")
        self.entryPWD.insert(0, "toto")
        self.entryLogin.insert(0, "toto")

        self.labelLogin.grid(row=1, sticky=E)
        self.labelPWD.grid(row=2, sticky=E)
        self.labelIP.grid(row=3, sticky=E)

        self.entryLogin.grid(row=1, column=1)
        self.entryPWD.grid(row=2, column=1)
        self.entryIP.grid(row=3, column=1)

        self.buttonConnect = Button(self, text="Se Connecter", fg="red", command=self.connectToServer)
        self.buttonConnect.pack(side="left")

        self.buttonQuit = Button(self, text="Quitter", command=self.quit)
        self.buttonQuit.pack(side="right")

    def connectToServer(self):
        login = self.entryLogin.get()
        pwd = self.entryPWD.get()
        ip = self.entryIP.get()

        if (login and pwd):
            print("Hello " + self.entryLogin.get())
            msg = login + "\n1\n" + pwd
            self.controller.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.controller.client.connect((ip, port))
            self.controller.client.send(msg.encode())
            self.controller.login = login + "\n1\n"
            self.controller.startReceiver()
            self.controller.changeFrame("VLController")

class VLController(tk.Frame):

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.controller = controller
        self.labelTitle = tk.Label(self, text="To control VLC", font=controller.title_font)
        self.labelTitle.pack(side="top", fill="x", pady=10)

        # Création de nos widgets
        self.frameVLCtrl = Frame(self, width=768, height=576, borderwidth=1)
        self.frameVLCtrl.pack(fill=BOTH)

        self.labelFile = Label(self.frameVLCtrl, text="File : ")
        self.labelTitre = Label(self.frameVLCtrl, text="Titre : ")
        self.labelArtist = Label(self.frameVLCtrl, text="Artist : ")
        self.labelGenre = Label(self.frameVLCtrl, text="Genre : ")
        self.labelAlbum = Label(self.frameVLCtrl, text="Album : ")
        self.labelCircle = Label(self.frameVLCtrl, text="Circle : ")
        self.labelComment = Label(self.frameVLCtrl, text="Comment : ")
        self.labelInstrumental = Label(self.frameVLCtrl, text="Instrumental : ")

        self.entryFile = Entry(self.frameVLCtrl)
        self.entryTitle = Entry(self.frameVLCtrl)
        self.entryArtist = Entry(self.frameVLCtrl)
        self.entryGenre = Entry(self.frameVLCtrl)
        self.entryCircle = Entry(self.frameVLCtrl)
        self.entryAlbum = Entry(self.frameVLCtrl)
        self.entryComment = Entry(self.frameVLCtrl)
        self.entryInstrumental = Entry(self.frameVLCtrl)

        self.labelFile.grid(row=1, sticky=E)
        self.labelTitre.grid(row=2, sticky=E)
        self.labelArtist.grid(row=3, sticky=E)
        self.labelGenre.grid(row=4, sticky=E)
        self.labelAlbum.grid(row=5, sticky=E)
        self.labelCircle.grid(row=6, sticky=E)
        self.labelComment.grid(row=7, sticky=E)
        self.labelInstrumental.grid(row=8, sticky=E)

        self.entryFile.grid(row=1, column=1)
        self.entryTitle.grid(row=2, column=1)
        self.entryArtist.grid(row=3, column=1)
        self.entryGenre.grid(row=4, column=1)
        self.entryAlbum.grid(row=5, column=1)
        self.entryCircle.grid(row=6, column=1)
        self.entryComment.grid(row=7, column=1)
        self.entryInstrumental.grid(row=8, column=1)

        self.dicoEntry = {}
        self.dicoEntry["filename"] = self.entryFile
        self.dicoEntry["title"] = self.entryTitle
        self.dicoEntry["artist"] = self.entryArtist
        self.dicoEntry["album"] = self.entryAlbum
        self.dicoEntry["genre"] = self.entryGenre
        self.dicoEntry["comment"] = self.entryComment
        self.dicoEntry["circle"] = self.entryCircle
        self.dicoEntry["langage"] = self.entryInstrumental

        self.labelDebug = Label(self.frameVLCtrl, text="debug : ")
        self.entryDebug = Entry(self.frameVLCtrl)
        self.labelDebug.grid(row=9, sticky=E)
        self.entryDebug.grid(row=9, column=1)

        self.frameButtonCtrl = Frame(self, width=768, borderwidth=1)
        self.frameButtonCtrl.pack(fill=BOTH)

        self.buttonPrev = Button(self.frameButtonCtrl, text="<<", command=self.prev)
        self.buttonPrev.pack(side="left")
        self.buttonPlay = Button(self.frameButtonCtrl, text="Play", command=self.play)
        self.buttonPlay.pack(side="left")
        self.buttonNext = Button(self.frameButtonCtrl, text=">>", command=self.next)
        self.buttonNext.pack(side="left")
        self.buttonModify= Button(self.frameButtonCtrl, text="Modify", fg="red", command=self.sendTest)
        self.buttonModify.pack(side="left")
        self.buttonPlaylist = Button(self.frameButtonCtrl, text="Playlist", command=self.sendTest)
        self.buttonPlaylist.pack(side="left")
        self.buttonMove = Button(self.frameButtonCtrl, text="Move", fg="red", command=self.sendTest)
        self.buttonMove.pack(side="left")
        self.buttonRemove = Button(self.frameButtonCtrl, text="Del", fg="red", command=self.remove)
        self.buttonRemove.pack(side="left")

        self.labelDirectory = Label(self.frameVLCtrl, text="Directory  : ")
        self.entryDirectory = Entry(self.frameVLCtrl)
        self.labelDirectory.grid(row=10, sticky=E)
        self.entryDirectory.grid(row=10, column=1)
        self.buttonSend = Button(self, text="Send", command=self.sendCMD)
        self.buttonSend.pack(side="left")
        self.buttonDirectory = Button(self, text="Open", command=self.opendirectory)
        self.buttonDirectory.pack(side="left")
        self.buttonSend = Button(self, text="Start", command=self.startVLC)
        self.buttonSend.pack(side="left")
        self.buttonStop = tk.Button(self, text="Stop", fg="red", command=self.controller.stopServices)
        self.buttonStop.pack(side="right")
        self.buttonQuit = tk.Button(self, text="Disconnect", command=self.controller.disconnect)
        self.buttonQuit.pack(side="right")

    def opendirectory(self):
        fileopen = ""
        try:
            self.entryDirectory.delete(0, END)
            fileopen = filedialog.askdirectory(parent=self)
            self.entryDirectory.insert(END, fileopen)
        except:
            self.entryDirectory.insert(END, "There was an error opening ")
            self.entryDirectory.insert(END, fileopen)

    def updateInfos(self, infos):
        for key in self.dicoEntry:
            self.dicoEntry[key].delete(0, END)

        for info in infos:
            tmp = info.split("\n2\n")
            if tmp[0] in self.dicoEntry.keys():
                self.dicoEntry[tmp[0]].insert(0, tmp[1])

    def sendTest(self):
        msg = self.controller.login + "Test"
        self.controller.client.send(msg.encode())

    def startVLC(self):
        msg = self.controller.login + "VLC\n1\nstart\n1\n" + self.entryDirectory.get()
        self.controller.client.send(msg.encode())

    def next(self):
        msg = self.controller.login + "VLC\n1\nnext"
        self.controller.client.send(msg.encode())

    def prev(self):
        msg = self.controller.login + "VLC\n1\nprev"
        self.controller.client.send(msg.encode())

    def play(self):
        msg = self.controller.login + "VLC\n1\nplay"
        self.controller.client.send(msg.encode())

    def remove(self):
        msg = self.controller.login + "Music\n1\nremove"
        self.controller.client.send(msg.encode())

    def checked(self):
        msg = self.controller.login + "Music\n1\nchecked"
        self.controller.client.send(msg.encode())

    def sendCMD(self):
        msg = self.controller.login + self.entryDebug.get()
        msg = msg.replace("*", "\n1\n")
        self.controller.client.send(msg.encode())

if __name__ == "__main__":
    interface = GUI()
    interface.mainloop()
