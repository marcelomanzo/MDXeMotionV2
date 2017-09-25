""" Platform Controller connects a selected client to chair.

This version requires NoLimits attraction license and NL ver 2.5.3.4 or later
"""

import sys
import time
import copy
import Tkinter as tk
import ttk
import tkMessageBox
import traceback
import numpy as np
from math import degrees

sys.path.insert(0, './client')  # the relative dir containing client files
sys.path.insert(0, './coaster')  # the relative dir containing coaster files
sys.path.insert(0, './temperature') #relative path to cpu and gpu monitor

#  from platform_input_tk import InputInterface   #  tkinter gui
#  from platform_input import InputInterface    #  keyboard
#  from platform_input_UDP import InputInterface #  UDP
#  from platform_input_threadedUDP import InputInterface #  threaded UDP
from coaster_client import InputInterface
from kinematics import Kinematics
from shape import Shape
from platform_output import OutputInterface

from temperature import system_temperature

isActive = True  # set False to terminate
frameRate = 0.05

client = InputInterface()
chair = OutputInterface()
shape = Shape(frameRate)
k = Kinematics()

temperature = system_temperature((40,60),(75,90))

class Controller:

    def __init__(self):
        self.prevT = 0
        self.is_output_enabled = False
        geometry = chair.get_geometry()
        k.set_geometry( geometry[0],geometry[1],geometry[2])
        limits = chair.get_limits()
        shape.begin(limits, "shape.cfg")
        client.begin(self.cmd_func, self.move_func, limits)

    def init_gui(self, root):
        self.root = root
        self.root.geometry("580x320")
        self.root.iconbitmap('images\ChairIcon3.ico')
        title = client.rootTitle + " for " + chair.get_platform_name()
        self.root.title(title)
        print title
        nb = ttk.Notebook(root)
        page1 = ttk.Frame(nb)  # client
        nb.add(page1, text='  Input  ')
        page2 = ttk.Frame(nb)  # shape
        nb.add(page2, text='  Shape  ')
        page3 = ttk.Frame(nb)  # output
        nb.add(page3, text='  Output ')
        nb.pack(expand=1, fill="both")

        client.init_gui(page1)
        shape.init_gui(page2)
        chair.init_gui(page3)

    def update_gui(self):
        self.root.update_idletasks()
        self.root.update()

    def quit(self):
        if client.USE_GUI:
            result = tkMessageBox.askquestion("Shutting Down Platform Software", "Are You Sure you want to quit?", icon='warning')
            if result != 'yes':
                return
        global isActive
        isActive = False

    def enable_platform(self):
        pos = client.get_current_pos()
        actuator_lengths = k.inverse_kinematics(self.process_request(pos))
        #  print "cp", pos, "->",actuator_lengths
        chair.set_enable(True, actuator_lengths)
        self.is_output_enabled = True
        #  print "enable", pos

    def disable_platform(self):
        pos = client.get_current_pos()
        #  print "disable", pos
        actuator_lengths = k.inverse_kinematics(self.process_request(pos))
        chair.set_enable(False, actuator_lengths)
        self.is_output_enabled = False
    
    def move_to_idle(self):
        actuator_lengths = k.inverse_kinematics(self.process_request(client.get_current_pos()))
        chair.move_to_idle(actuator_lengths)
        # chair.show_muscles([0,0,0,0,0,0], actuator_lengths)
        
    def move_to_ready(self):
        actuator_lengths = k.inverse_kinematics(self.process_request(client.get_current_pos()))
        chair.move_to_ready(actuator_lengths)
        
    def swell_for_access(self):
        chair.swell_for_access(4)  # four seconds in up pos

    def process_request(self, request):
        #  print "in process"
        if client.is_normalized:
            #  print "pre shape", request,
            request = shape.shape(request)  # adjust gain & washout and convert from norm to real
            #  print "post",request       
        request = shape.smooth(request)
        ##if self.is_output_enabled:
        return request

    def move(self, position_request):
        #  position_requests are in mm and radians (not normalized)
        start = time.time()
        #  print "req= " + " ".join('%0.2f' % item for item in position_request)
        actuator_lengths = k.inverse_kinematics(position_request)
        if client.USE_GUI:
            chair.show_muscles(position_request, actuator_lengths)
            controller.update_gui()
        chair.move_platform(actuator_lengths)

        #  print "dur =",  time.time() - start, "interval= ",  time.time() - self.prevT
        #  self.prevT =  time.time()

    def cmd_func(self, cmd):  # command handler function called from Platform input
        global isActive
        if cmd == "exit":
            isActive = False
        elif cmd == "enable":
            controller.enable_platform()
        elif cmd == "disable":
            controller.disable_platform()
        elif cmd == "idle":
            controller.move_to_idle()
        elif cmd == "ready":
            controller.move_to_ready()
        elif cmd == "swellForStairs":
            controller.swell_for_access()
        elif cmd == "quit":
            # prompts with tk msg box to confirm 
            controller.quit() 

    def move_func(self, request):  # move handler to position platform as requested by Platform input
        #  print "request is trans/rot list:", request
        try:
            request = np.array(request)
            r = controller.process_request(request)
            controller.move(r)
        except:
            e = sys.exc_info()[0]  # report error
            s = traceback.format_exc()
            print e, s

controller = Controller()


def main():

    try:      
        if client.USE_GUI:
            root = tk.Tk()
            controller.init_gui(root)
    except NameError:
        client.USE_GUI = False
        print "GUI Disabled"

    previous = time.time()
    chair_status = None
    ###client.service()
    ###controller.disable_platform()
    frame = 0 
    while isActive:
        if client.USE_GUI:
            controller.update_gui()
        if(time.time() - previous >= frameRate *.99):
            #  print format("Frame duration = %.1f" % ((time.time() - previous)*1000))
            previous = time.time()
            """
            if chair_status != chair.get_output_status():
                chair_status = chair.get_output_status()
                client.chair_status_changed(chair_status)
            """
            client.service()
            if frame % int(1/frameRate) == 0:
                 # hack to display temperature on Festo status line"
                status = temperature.read()
                colors = ["green3","orange","red"]
                client.chair_status_changed((status[0], colors[status[1]]))
                #print temperature.read()[0]
                
            frame += 1
            #  print format("in controller, service took %.1f ms" % ((time.time() - previous) * 1000))


if __name__ == "__main__":
    main()
    client.fin()
    chair.fin()
