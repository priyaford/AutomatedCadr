import paho.mqtt.client as mqtt
from Crypto.Cipher import AES
import bluepy
from bluepy import btle
from bluepy.btle import Scanner, DefaultDelegate, Peripheral
import binascii
import os
import time
import threading
import sys
from multiprocessing import Queue
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import random

from . import oad as oad
from . import scannerFunctions as fxn
from . import scannerClasses as cls
from ..functions import commonFunctions as comFxn
from ..config import mainConfig as mainConfig

## @scanner
# Main file for scanner for detecting devices nearby for system testing
# the system test is running as long as the device is detectable on bluetooth, 
# every {scanTime} the scanner updates with devices nearby to Mqtt channel.
# 
# The scanner also do bluetooth actions on the devices, after each scan period
# the scanner wait {scanTime} seconds for commands to run on the devices.
# commands are retreived from individual command channels, where ble address to perform command on
# is posted.


scannerQ = Queue()

def RunScanner(config):   
    waitQueue = Queue()
    client = mqtt.Client()
    client.on_connect = fxn.onConnect
    client.on_message = fxn.onMessage
    client.connect("127.0.0.1", 1883)
    client.loop_start()

    publicKey = [0x39, 0x2F, 0xC5, 0xD4, 0x5F, 0xA5, 0x55, 0x44, 0x26, 
                0x90, 0xA6, 0xBC, 0xA9, 0x41, 0xAB, 0xB6]

    bleDevicesFound = {}

    text = b'\x1a\x71\xbd\xd3\xc7\x9c\x1b\x94\xc6\x5c\xd8\x3a\xbb\xeb\x3b\x7a'
    key = b'\x39\x2F\xC5\xD4\x5F\xA5\x55\x44\x26\x90\xA6\xBC\xA9\x41\xAB\xB6'
    IV = 16 * '\x00'           # Initialization vector: discussed later
    mode = AES.MODE_ECB
    '''encryptor = AES.new(key, mode, IV=IV)
    text = 'j' * 64 + 'i' * 128
    ciphertext = encryptor.encrypt(text)
    '''
    decryptor = AES.new(key, mode)
    plain = decryptor.decrypt(text)
    imei = plain[0:7]
    imsi = plain[8:16]
    #imeiNumber = int.from_bytes(imei, byteorder='big')
    #print(imeiNumber)

    #add loop for adding multiple imei
    client.publish("Scanner/log", "Starting scanner")
    client.subscribe("bleControl/reset")
    client.subscribe("bleControl/factoryReset")
    client.subscribe("bleControl/toggleSiren")
    client.subscribe("bleControl/wakeup")
    client.subscribe("bleControl/oad")
    client.subscribe("bleControl/dummy")
    client.subscribe("Manual/reset")
    scanner = Scanner().withDelegate(ScanDelegate(client))
    while(1):
        devices = None
        for i in range(0,3):
            try:
                comFxn.Debug("Scanner", "round increment")
                devices = scanner.scan(timeout=mainConfig.scanTime)
                break
            except:
                continue
        CheckDevices(devices, config, client)
        runScannerQ(client)
        comFxn.Debug("Scanner", "scanner done, waiting for commands")
        time.sleep(mainConfig.waitTime)
        #cls.scannerIncomingQ.put("bleControl/oad")
        #cls.scannerIncomingQ.put("f0:f8:f2:bf:a0:d7 ce5e3a09cc0c430f7328b7993d70879c") 
        '''cls.scannerIncomingQ.put("bleControl/oad")       
        cls.scannerIncomingQ.put("f0:f8:f2:bf:9b:32 6b8537a19c5714b04e45bcb5586133d2")
        cls.scannerIncomingQ.put("bleControl/oad")
        cls.scannerIncomingQ.put("a4:da:32:06:f4:51 5c580c35b1c83a6c648eda6baed3f74c")
        cls.scannerIncomingQ.put("bleControl/oad")
        cls.scannerIncomingQ.put("e0:7d:ea:f2:e9:a1 77e3218cf22a4b007f7e48bde72026b2")
        cls.scannerIncomingQ.put("bleControl/oad")
        cls.scannerIncomingQ.put("a4:da:32:06:e8:bb b722862f11aacde859f39d0ede10def7") 
        cls.scannerIncomingQ.put("bleControl/oad")  
        cls.scannerIncomingQ.put("e0:7d:ea:f2:ee:a3 deeac4e425b830ee2c108069e2270739")
        cls.scannerIncomingQ.put("bleControl/oad")
        cls.scannerIncomingQ.put("a4:da:32:06:e7:a3 46d7c4e06e170cf3703dd7cf1257a995")
        #cls.scannerIncomingQ.put("bleControl/oad")
        #cls.scannerIncomingQ.put("a4:da:32:06:e5:ce a41f2168e8833243bbf33e1db8dd2144")
        #cls.scannerIncomingQ.put("bleControl/oad")
        #cls.scannerIncomingQ.put("e0:7d:ea:f2:ee:9e 5761dbc453be9cb70b148d0c41356b1a")
        cls.scannerIncomingQ.put("bleControl/oad")
        cls.scannerIncomingQ.put("80:6f:b0:ad:a4:cf 893a72f19d175988458905635451689e")
        cls.scannerIncomingQ.put("bleControl/oad")
        cls.scannerIncomingQ.put("80:6f:b0:ad:86:ea 4ad4da572536b5362f74f87a3894bb9c")'''
        comFxn.Debug("Scanner", "Handling Queue")
        HandleIncomingQueue(client, config) 


    

class ScanDelegate(DefaultDelegate):
    def __init__(self, client):
        DefaultDelegate.__init__(self)
        self.client = client
    def handleDiscovery(self, dev, isNewDev, isNewData):
        pass

def runScannerQ(client):
    while not scannerQ.empty():        
        msg = scannerQ.get_nowait()
        client.publish("Scanner/device", msg)

def CheckDevices(devices, config, client):
    for dev in devices:
        for (adtype, desc, value) in dev.getScanData():
            #print(desc, value)
            if desc is "Manufacturer":
                #print(value)
                if fxn.checkBleManufacturer(value):
                    try:
                        deviceId = value[4:36]
                    except:
                        continue
                    print(deviceId, " ", end='')
                    if deviceId not in config.testDevices.values():
                        print(" not in testDevices")
                        continue
                    print(" is in testDevices")
                    battery = int(value[36:38],16)
                    eventNr = int(value[38:40],16)                    
                    eventLoop = config.loopEvents.get(eventNr, eventNr)
                    charging = False
                    if battery != 0xFF:
                        charging = True if battery > 100 else False
                        battery = battery - 0x80 if battery > 100  else battery
                    try:
                        doc = config.db.document(u'devices' + '/' + deviceId).get()
                        stage = doc.get(u'systemTest.stage')                            
                        comFxn.Debug("Scanner ", "Devices "+ str(deviceId) +  " bleAddr: " + str(dev.addr)+" stage: " + stage)
                        lastContact = doc.get(u'latestData.timestamp')
                        msg =  str(deviceId) + " ba: " + str(dev.addr) + " RSSI: " + str(dev.rssi) \
                            + " Battery: " + str(battery) + " eventLoop: " + str(eventLoop) + " Ch: " + str(charging) +" serverContact:" + str(lastContact)
                        scannerQ.put(msg)
                    except Exception as err:
                        print(err)
                        print("could not get stuff from server")
                        pass
                else:
                    print("")

def HandleIncomingQueue(client, config):
    peripheral = None
    handledArray = []
    while not cls.scannerIncomingQ.empty():
            try:
                topic = cls.scannerIncomingQ.get_nowait()
                print("Scanner got in queue: ", topic)
                if topic == "bleControl/reset" or topic == "bleControl/factoryReset" \
                    or topic == "bleControl/wakeup" or topic == "bleControl/toggleSiren" \
                    or topic == "Manual/reset":
                    payload = cls.scannerIncomingQ.get()
                    arr = payload.split(" ")
                    bleAddr = arr[0]
                    try:
                        deviceId = arr[1]
                    except:
                        deviceId = "unknown"
                    if deviceId in handledArray:
                        comFxn.Debug("Scanner", deviceId, " already handled this round")
                        continue
                    handledArray.append(deviceId)
                    comFxn.Debug("Scanner ", "Bluetooth action on ", bleAddr, " ", deviceId)
                    try:    
                        print("doing bluetooth")
                        if fxn.doBluetooth(bleAddr, deviceId, topic, client, config.db):
                            client.publish("Scanner/log", "Done,continuing with scanner")
                        else:                    
                            client.publish("Scanner/ERROR", "BluetoothProblem")
                    except btle.BTLEDisconnectError as err:
                        print(err)
                        client.publish("Scanner/ERROR", "Bluetooth error")
                        raise fxn.BluetoothError("Disconnection 4")
                    except btle.BTLEException as err:
                        print(err)  
                        client.publish("Scanner/ERROR", "Bluetooth error")
                        raise fxn.BluetoothError("Disconnection 5")
                    except Exception as err:
                        print(err)
                        client.publish("Scanner/ERROR", "Bluetooth error")
                        raise fxn.BluetoothError("Disconnection 6")
                        #error with doing bluetooth
                if topic == "bleControl/oad": 
                    payload = cls.scannerIncomingQ.get()
                    arr = payload.split(" ")
                    bleAddr = arr[0]
                    deviceId = arr[1]
                    if deviceId in handledArray:
                        comFxn.Debug("Scanner", deviceId, " already handled this round")
                        continue
                    handledArray.append(deviceId)
                    msg = "Bluetooth OAD action on " + str(bleAddr) + " " + str(deviceId)
                    comFxn.Debug("Scanner ", msg)  
                    client.publish("Scanner/log", msg)
                    try:
                        peripheral = Peripheral()
                        oad.doOad(bleAddr, deviceId, client, peripheral, config)
                        msg = "bleControl/oad "  + bleAddr + " pass " + " all is Ok " 
                        client.publish("Scanner/status", msg)
                        try:
                            peripheral.disconnect()
                        except:
                            pass
                    except btle.BTLEException as err:
                        print(err)
                        msg = "bleControl/oad"  + " " + bleAddr + " fail " + str(err) 
                        client.publish("Scanner/status", msg)
                        client.publish("Scanner/ERROR", "Bluetooth error")
                        raise cls.OadError(msg)
                    except btle.BTLEDisconnectError as err:
                        print(err)
                        msg = "bleControl/oad"  + " " + bleAddr + " fail " + str(err)  
                        client.publish("Scanner/status", msg)
                        client.publish("Scanner/ERROR", "Bluetooth error")
                        raise cls.OadError(msg)
                    except Exception as err:
                        msg = str(err)
                        msg = "bleControl/oad"  + " " + bleAddr + " fail " + str(err) 
                        client.publish("Scanner/status", msg)
                        client.publish("Scanner/ERROR", msg)
                        raise cls.OadError(msg)
            except Exception as err:
                try:
                    peripheral.disconnect()
                except:
                    pass
                print(err)
                continue
    CheckAdvertisements(mainConfig.testDevices.values(), handledArray)

def CheckAdvertisements(testDevices, advertised):
    for device in testDevices:
        if device in advertised:
            continue
        comFxn.Debug("Scanner: not handled device ", device)
