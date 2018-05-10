from tkinter import *

import tkinter as tk
from tkinter import font  as tkfont
import socket
import subprocess
import netifaces as ni
from threading import *

# Todo remove it..
def getVarEnvironnement(var):
  return subprocess.check_output("echo $" + var, shell=True).decode().strip()

interface = getVarEnvironnement("interface")
host = "127.0.0.1"
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
port = 8888


class GUI(tk.Tk):

    def __init__(self, *args, **kwargs):
        tk.Tk.__init__(self, *args, **kwargs)
        self.thread1 = None
        self.stop_threads = Event()
        self.login = ""
        self.title_font = tkfont.Font(family='Helvetica', size=18, weight="bold", slant="italic")

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
                text = s.recv(1024).decode()
                if not text: break
                print("Receive : " + text)
            except:
                break

    def startReceiver(self):
        self.stop_threads.clear()
        self.thread1 = Thread(target = self.receive)
        self.thread1.start()

    def stopReceiver(self):
        msg = self.login + "end"
        s.send(msg.encode())
        self.stop_threads.set()
        self.thread1.join()
        self.thread1 = None
        s.close()

    def changeFrame(self, page_name):
        '''Show a frame for the given page name'''
        frame = self.frames[page_name]
        frame.tkraise()


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

        self.entryLogin = Entry(self.frameConnect)
        self.entryPWD = Entry(self.frameConnect)


        self.labelLogin.grid(row=1, sticky=E)
        self.labelPWD.grid(row=2, sticky=E)

        self.entryLogin.grid(row=1, column=1)
        self.entryPWD.grid(row=2, column=1)

        self.buttonConnect = Button(self, text="Se Connecter", fg="red", command=self.connectToServer)
        self.buttonConnect.pack(side="left")

        self.buttonQuit = Button(self, text="Quitter", command=self.quit)
        self.buttonQuit.pack(side="right")

    def connectToServer(self):
        login = self.entryLogin.get()
        pwd = self.entryPWD.get()

        if (login and pwd):
            print("Hello " + self.entryLogin.get())
            msg = login + "." + pwd
            s.connect((host, port))
            s.send(msg.encode())
            self.controller.login = login + "."
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

        self.labelDebug = Label(self.frameVLCtrl, text="debug :")
        self.entryDebug = Entry(self.frameVLCtrl)
        self.labelDebug.grid(row=1, sticky=E)
        self.entryDebug.grid(row=1, column=1)

        self.buttonSend = Button(self, text="Send", fg="red", command=self.sendCMD)
        self.buttonSend.pack(side="left")
        self.buttonQuit = tk.Button(self, text="Disconnect", command=self.quit)
        self.buttonQuit.pack()

    def sendCMD(self):
        msg = self.controller.login + self.entryDebug.get()
        s.send(msg.encode())

    def quit(self):
        self.controller.stopReceiver()
        self.controller.quit()

if __name__ == "__main__":
    interface = GUI()
    interface.mainloop()
