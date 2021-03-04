# hello_psg.py

from os import device_encoding
import PySimpleGUI as sg
import numpy
from src.config import mainConfig as mainConfig

class Device():
    def __init__(self, imei, deviceId):
        self.imei = imei
        self.deviceId = deviceId

imeiArray = []
deviceIdArray = []
for stuff in  mainConfig.testDevices.keys():
    imeiArray.append(stuff)
for stuff in  mainConfig.testDevices.values():
    deviceIdArray.append(stuff)
    
device1 = Device(imeiArray[0],deviceIdArray[0])
device2 = Device(imeiArray[1],deviceIdArray[1])
device3 = Device(imeiArray[2],deviceIdArray[2])
device4 = Device(imeiArray[3],deviceIdArray[3])
device5 = Device(imeiArray[4],deviceIdArray[4])
device6 = Device(imeiArray[5],deviceIdArray[5])
device7 = Device(imeiArray[6],deviceIdArray[6])
device8 = Device(imeiArray[7],deviceIdArray[7])
device9 = Device(imeiArray[8],deviceIdArray[8])
device10 = Device(imeiArray[9],deviceIdArray[9])

layout = [
    #device 1
    [sg.Text(device1.deviceId)], 
    [sg.Text(device2.deviceId)], 
    [sg.Text(device3.deviceId)], 
    [sg.Text(device4.deviceId)], 
    [sg.Text(device5.deviceId)], 
    [sg.Text(device6.deviceId)], 
    [sg.Text(device7.deviceId)], 
    [sg.Text(device8.deviceId)], 
    [sg.Text(device9.deviceId)], 
    [sg.Text(device10.deviceId)],  
    [sg.Text(device10.deviceId)],
    [sg.Text(device10.deviceId)],   
    [sg.Button("OK")]
    ]

# Create the window
window = sg.Window("Demo", layout, margins=(700,400) )
# Create an event loop
while True:
    event, values = window.read()
    # End program if user closes window or
    # presses the OK button
    if event == "OK" or event == sg.WIN_CLOSED:
        break

window.close()
