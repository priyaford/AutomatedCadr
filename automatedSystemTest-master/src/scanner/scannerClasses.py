from bluepy.btle import Scanner, DefaultDelegate
from multiprocessing import Queue
from threading import Timer
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

scannerQ = Queue()
scannerIncomingQ = Queue()
runScannerQ = Queue()
##errorClass
class OadError(Exception):
    pass

##errorClass
class DatabaseError(Exception):
    pass

##errorClass
class BluetoothError(Exception):
    pass

class Watchdog:
    def __init__(self, timeout, userHandler=None):  # timeout in seconds
        self.timeout = timeout
        self.handler = userHandler if userHandler is not None else self.defaultHandler
        self.timer = Timer(self.timeout, self.handler)
        self.timer.start()

    def reset(self):
        self.timer.cancel()
        self.timer = Timer(self.timeout, self.handler)
        self.timer.start()

    def stop(self):
        self.timer.cancel()

    def defaultHandler(self):
        raise self

class Device:
    def __init__(self):
        self.deviceId = " "
        self.imei = 0
        self.bleAddr = ""
        self.deviceid = ""
        self.eventLoop = ""
        self.battery = ""


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