# Add link to sentdex youtube
#https://www.youtube.com/watch?v=A0gaXfM1UN0&index=2&list=PLQVvvaa0QuDclKx-QpC9wntnURXVJqLyk
#TODO Tutorial 19 adds help button option to walk through gui
import tkinter as tk
from tkinter import ttk

import matplotlib
matplotlib.use("TkAgg")
from matplotlib import pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2TkAgg
from matplotlib.figure import Figure
import matplotlib.animation as animation
from matplotlib import style
from PIL import Image, ImageTk

from abr_control.utils import DataHandler

dat = DataHandler(use_cache=True)

LARGE_FONT = ("Verdana", 12)
MED_FONT = ("Verdana", 10)
SMALL_FONT = ("Verdana", 8)
style.use("ggplot")

f = Figure(figsize=(5,5), dpi=100)
a = f.add_subplot(111)

# global variable for searching in db
loc = ['/']

def animate(i):
    pullData = open("SampleData.txt", "r").read()
    dataList = pullData.split('\n')
    xList = []
    yList = []
    for eachLine in dataList:
        if len(eachLine) > 1:
            x, y = eachLine.split(',')
            xList.append(int(x))
            yList.append(int(y))
    a.clear()
    a.plot(xList, yList)
    # a.legend(bbox_to_anchor=(0,1.02,1,.102), loc=3)

def popupmsg(msg):
    popup = tk.Tk()

    print(msg)
    popup.wm_title("!")
    print(msg)
    label = tk.Label(popup, text=msg, font=MED_FONT)
    print(msg)
    label.pack(side="top", fill="x", pady=10)
    print(msg)
    B1 = ttk.Button(popup, text='OK', command=popup.destroy)
    print(msg)
    B1.pack()
    print(msg)
    popup.mainloop()
    print(msg)

# def change_param(param):
#     global param_to_plot
#     param_to_plot = param
#
# def get_db_loc(loc):
#     global loc
#
# def update_plot_param_menu(self):
#     if loc == '/':
#         self.param_menu.delete()
#

def go_back_loc_level(self):
    global loc
    loc = loc[:-1]
    self.entry.delete(0, 'end')
    self.update_list()

def add_img(self, size=[200,200], file_loc='test_img.jpg', row=0, column=0, *args):
    img = Image.open(file_loc)
    img = img.resize((size[0], size[1]), Image.ANTIALIAS)
    img = ImageTk.PhotoImage(img)
    label = tk.Label(self, image=img, width=size[0], height=size[1])
    label.image = img
    label.grid(row=row, column=column)

class Page(tk.Tk):

    def __init__(self, *args, **kwargs):

        tk.Tk.__init__(self, *args, **kwargs)
        tk.Tk.wm_title(self, 'abr_control data')

        container = tk.Frame(self)
        container.grid(row=0, column=0, sticky='nsew')
        # container.pack(side="top", fill="both", expand=True)
        # container.grid_rowconfigure(0, weight=1)
        # container.grid_columnconfigure(0, weight=1)

        # menu bar at top
        menubar = tk.Menu(container)
        # define main file menu
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Save Figure",
                command=lambda:popupmsg(msg="Not Supported Yet"))
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=quit)
        # place file menu
        menubar.add_cascade(label="File", menu=filemenu)

        # # define parameter to plot menu
        # self.param_menu = tk.Menu(menubar, tearoff=1)
        # self.param_menu.add_command(label="None",
        #         command=lambda:popupmsg(
        #             msg=("There are no parameters to select from from the"
        #             + " current database group")))
        # self.param_menu.add_command(label="Error",
        #         command=lambda:changeParam("error"))
        # # place parameter menu bar
        # menubar.add_cascade(label="Plotting Parameters", menu=self.param_menu)

        tk.Tk.config(self, menu=menubar)

        self.frames = {}

        for F in (StartPage, SearchPage, PlotPage):
            frame = F(container, self)
            self.frames[F] = frame
            frame.grid(row=0, column=0, sticky="nsew")
        self.show_frame(StartPage)

    def show_frame(self, cont):
        frame = self.frames[cont]
        frame.tkraise()

class StartPage(tk.Frame):

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        label = tk.Label(self, text="Home", font=LARGE_FONT)
        label = tk.Label(self, text=('Welcome to the abr_control plotting GUI!'
            +'\n\nBrowse through your recorded tests in the \'Search\' Page. Any'
            + ' corresponding images that are saved to the test will be '
            + 'displayed'
            + '\n\nSwitch to the plotting screen to see a live plot of your'
            + ' selected tests'
            + '\n\nThe default plotting parameter is First Order Error, but this'
            + ' can be changed through the check boxes along the side of the'
            + ' \'Plotting\' page'), font=MED_FONT)
        label.grid(row=1, column=0)

        button2 = ttk.Button(self, text="Search",
                command=lambda: controller.show_frame(SearchPage))
        button2.grid(row=2,column=0)
        button3 = ttk.Button(self, text="Plot",
                command=lambda: controller.show_frame(PlotPage))
        button3.grid(row=3,column=0)

        add_img(self, file_loc='abr_logo.jpg', row=0, column=0)

class SearchPage(tk.Frame):

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        label = tk.Label(self, text="Search", font=LARGE_FONT)
        label.grid(row=0, column=1, sticky='nsew')

        button1 = ttk.Button(self, text="Home",
                command=lambda: controller.show_frame(StartPage))
        button1.grid(row=1, column=1, sticky='nsew')
        button2 = ttk.Button(self, text="Back",
                command=lambda: go_back_loc_level(self))
        button2.grid(row=1, column=0, sticky='nsew')
        button3 = ttk.Button(self, text="Plot",
                command=lambda: controller.show_frame(PlotPage))
        button3.grid(row=1, column=2, sticky='nsew')

        self.search_var = tk.StringVar()
        self.search_var.trace("w", self.update_list)
        # self.selected_var = tk.StringVar()
        # self.selected_var.trace("w", self.get_selection)
        self.entry = tk.Entry(self, textvariable=self.search_var, width=13)
        self.lbox = tk.Listbox(self, width=45, height=15, selectmode='MULTIPLE')
        self.lbox.bind('<<ListboxSelect>>', self.get_selection)

        self.entry.grid(row=3, column=0, sticky='nsew', columnspan=3)
        self.lbox.grid(row=4, column=0, sticky='nsew', columnspan=3)

        # Function for updating the list/doing the search.
        # It needs to be called here to populate the listbox.
        self.update_list()
        values = [self.lbox.get(idx) for idx in self.lbox.curselection()]

    def get_selection(self, *args):
        global loc
        index = int(self.lbox.curselection()[0])
        value = self.lbox.get(index)
        print('You selected item %d: "%s"' % (index, value))
        loc.append('%s/'%value)
        self.entry.delete(0, 'end')
        self.update_list()

    def update_list(self, *args):
        global loc
        search_term = self.search_var.get()

        # pull keys from the database
        lbox_list_tmp = dat.get_keys(''.join(loc))

        if lbox_list_tmp is not None:
            print('loc points to group')
            lbox_list = lbox_list_tmp

            self.lbox.delete(0, tk.END)

            for item in lbox_list:
                if search_term.lower() in item.lower():
                    self.lbox.insert(tk.END, item)
        # if the current path points to a dataset then go back one level
        else:
            print('loc points to dataset')
            go_back_loc_level(self)
            self.update_list()

class PlotPage(tk.Frame):

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        label = tk.Label(self, text="Plot", font=LARGE_FONT)
        label.pack(pady=10, padx=10)

        button1 = ttk.Button(self, text="Home",
                command=lambda: controller.show_frame(StartPage))
        button1.pack()
        button3 = ttk.Button(self, text="Search",
                command=lambda: controller.show_frame(SearchPage))
        button3.pack()

        canvas = FigureCanvasTkAgg(f, self)
        canvas.show()
        canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # show the matplotlib toolbar
        toolbar = NavigationToolbar2TkAgg(canvas, self)
        toolbar.update()
        canvas._tkcanvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

app = Page()
#app.geometry("1280x720")
ani = animation.FuncAnimation(f, animate, interval=1000)
app.mainloop()
