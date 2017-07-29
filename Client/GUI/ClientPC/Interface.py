from tkinter import *

import tkinter as tk
from tkinter import font  as tkfont


class GUI(tk.Tk):

    def __init__(self, *args, **kwargs):
        tk.Tk.__init__(self, *args, **kwargs)

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
            self.controller.changeFrame("VLController")

class VLController(tk.Frame):

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.controller = controller
        self.labelTitle = tk.Label(self, text="To control VLC", font=controller.title_font)
        self.labelTitle.pack(side="top", fill="x", pady=10)
        self.buttonQuit = tk.Button(self, text="Disconnect", command=controller.quit)
        self.buttonQuit.pack()

if __name__ == "__main__":
    interface = GUI()
    interface.mainloop()