from src.entertest.EnterTest import SetServerSettings
import paho.mqtt.client as mqtt
import os
import time
import threading

from src.scanner import scanner as scannerMod
from src.controller import controller as controllerMod
from src.analyzer import analyzer as analyzerMod
from src.mqttLogger import mqttLogger as loggerMod
from src.config import mainConfig
from src.entertest import EnterTest as testSetup

   # The callback for when a PUBLISH message is received from the server.
def onMessage(client, userdata, msg):
    try:
        if msg.topic == "Scanner/log" and msg.payload == b'Exiting':  
            print("found exit") 
            time.sleep(5) #wait for shutdown
            scanner = threading.Thread(target=scannerFxn, args=(1,))
            scanner.start()
    except Exception as err:
        print(err)
        

def onConnect(client, userdata, flags, rc):
    print("Connected Wrapper to mqtt with result code "+str(rc))
    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    client.subscribe("$SYS/#") 



client = mqtt.Client()
client.on_connect = onConnect
client.on_message = onMessage
client.connect("127.0.0.1", 1883)
client.loop_start()


client.subscribe("Scanner/log")

def scannerFxn():
    try:
        scannerMod.RunScanner(mainConfig)
    except Exception as err:
        print(err)

def controllerFxn():
    try:
        controllerMod.RunController(mainConfig)
    except Exception as err:
        print(err)

def analyzerFxn():
    try:
        analyzerMod.RunAnalyzer(mainConfig)
    except Exception as err:
        print(err)

def loggerFxn():
    try:
        loggerMod.RunMqttLogger()
    except Exception as err:
        print(err)  


if __name__ == "__main__":
    setup = input("Do you want to set up devices?y/n \n")
    if setup == 'y':
        testSetup.SetUpDevices(mainConfig)
    server = input("do you want to set up server? y/n\ \n")
    if server == 'y':
        testSetup.SetServerSettings(mainConfig)
    try:
        scannerFxn()
    except Exception as err:
        print(err)