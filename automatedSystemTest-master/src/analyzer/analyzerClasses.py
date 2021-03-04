
from bluepy.btle import Scanner, DefaultDelegate
from multiprocessing import Queue

import firebase_admin
from firebase_admin import credentials, firestore
from firebase_admin.firestore import SERVER_TIMESTAMP

import datetime



analyzerQ = Queue()

## Data object for one device.
class Device:
    def __init__(self):
        self.deviceId = ""
        self.imei = ""
        self.bleAddr = ""
        self.deviceid = ""
        self.rssi = 0
        self.currentStage= ""
        self.nextStage = ""

# Status object for one event that has been run/happened.
class StatusLog():
    def __init__(self):
        self.bleAddr = ""
        self.type = ""
        self.event = ""
        self.timestamp = datetime.datetime.now()
        self.status = "PASS"
        self.reason = ""
    def SetLog(self, thisEvent, status, bleaddr):
        self.event = thisEvent
        self.bleAddr = bleaddr
        self.timestamp = datetime.datetime.now()
        self.status = status
    def to_dict(self):
        reasontxt = " ".join(self.reason)
        dest = {
            u'type' : self.type,
            u'event' : self.event,
            u'timestamp' : self.timestamp,
            u'status' : self.status,
            u'reason' : reasontxt
        }
        return dest

class Test:
    def __init__(self):
        self.noOfDevices = 0
        self.imei = ""
        self.devices = {}

    def addImei(self, imei):
        self.noOfDevices += 1
        key = str(self.noOfDevices)
        self.devices[key] = imei

    def printImeis(self):
        print("Devices for testing:\n")
        for key in self.devices:
            print( key + " " + self.devices[key] )


class ScanDelegate(DefaultDelegate):
    def __init__(self):
        DefaultDelegate.__init__(self)

    def handleDiscovery(self, dev, isNewDev, isNewData):
        if isNewDev:
            #print("Discovered device", dev.addr)
            pass
        elif isNewData:
            #print("Received new data from", dev.addr)
            pass