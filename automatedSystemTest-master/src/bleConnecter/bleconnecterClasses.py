from bluepy.btle import Scanner, DefaultDelegate
from multiprocessing import Queue

queue = Queue()

class Device:
    def __init__(self):
        self.deviceId = " "
        self.imei = 0
        self.bleAddr = ""
        self.deviceid = ""


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