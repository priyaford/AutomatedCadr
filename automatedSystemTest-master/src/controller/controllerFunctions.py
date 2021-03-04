import datetime
import binascii
from firebase_admin import firestore
import time
import os

from . import controllerClasses as cls

def generateLogName():
    badChars = [':', '.', ' ']
    fileString = str(datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S"))
    customString = input("Enter custom logName? Press enter if you want autogenerated name...\n")
    if customString:
        fileString = customString
    fileString = 'logs/' + fileString + '.txt'
    return fileString

def logmsg(name, text):
    with open(name, "a+") as file:
        file.write(text + '\n')
        file.close()
    #log to firebase

def exitFunction(f):
    logmsg(f, "exit")
    exit
    

def onConnect(client, userdata, flags, rc):
    print("Connected Controller to mqtt with result code "+str(rc))
    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    client.subscribe("$SYS/#")   

def onMessage(client, userdata, msg):
    try:
        if msg.topic == "Scanner/device":
            data = msg.payload.decode("utf-8")
            data = data.split()
            device = cls.Device()
            device.deviceId = data[0]
            device.bleAddr = data[2]
            device.rssi = data[4]
            device.battery  = data[6]
            device.eventLoop = data[8]
            cls.controllerQ.put(device)
        if msg.topic == "Watchdog/exit":
            time.sleep(10)        
            #os.system("sudo systemctl restart blescanner")    
    except Exception as err:
        print(err)




def checkBleManufacturer(text):
    if text[0]=='6' and text[1]=='f' and text[2]=='0'and text[3]=='5':
        return True
    return False


    