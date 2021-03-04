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

from src.config import mainConfig as mainConfig
from src.scanner import scannerClasses as cls
from src.scanner import scannerFunctions as fxn
from src.scanner import oad as oad
from src.functions import commonFunctions as comFxn

## @scanner
# Main file for scanner for detecting devices nearby for system testing
# the system test is running as long as the device is detectable on bluetooth, 
# every {scanTime} the scanner updates with devices nearby to Mqtt channel.
# 
# The scanner also do bluetooth actions on the devices, after each scan period
# the scanner wait {config.scanTime} seconds for commands to run on the devices.
# commands are retreived from individual command channels, where ble address to perform command on
# is posted.




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


scanner = Scanner() #.withDelegate(ScanDelegate())


while True:  
    try: 
        devices = {}   
        try: 
            client.publish("Scanner/log", "Scanning " + str(mainConfig.scanTime) +  " sec...")
            devices = scanner.scan(mainConfig.scanTime)
        except bluepy.btle.BTLEDisconnectError as err:
            client.publish("Scanner/ERROR", "Device disconnected 1")
            raise cls.BluetoothError("Scanner Error")
        except Exception as err:
            print(err, type(err))
            client.publish("Scanner/ERROR", "Bluetoothproblem resetting ble")
            os.system("sudo hciconfig hci0 reset")
            time.sleep(10)          
            try: 
                client.publish("Scanner/log", "Scanning ", str(mainConfig.scanTime) ," sec...")
                devices = scanner.scan(mainConfig.scanTime)
            except Exception as err:
                print(err)
                print("doing down and up hci0")
                os.system("sudo hciconfig hci0 down")
                time.sleep(10)
                os.system("sudo hciconfig hci0 up")
                time.sleep(5)
                raise cls.BluetoothError("Scanner Error")
        for dev in devices:
            charging = None
            #print("Device %s (%s), RSSI=%d dB" % (dev.addr, dev.addrType, dev.rssi))
            #only send device if set in a stage
            for (adtype, desc, value) in dev.getScanData():
                #print(desc, value)
                if desc is "Manufacturer":
                    #print(value)
                    if fxn.checkBleManufacturer(value):
                        deviceId = value[4:36]
                        if deviceId not in mainConfig.testDevices.values():
                            print("not in testConfig ", deviceId)
                            continue
                        battery = int(value[36:38],16)
                        eventNr = int(value[38:40],16)                    
                        eventLoop = mainConfig.loopEvents.get(eventNr, eventNr)
                        if battery != 0xFF:
                            charging = True if battery > 100 else False
                            battery = battery - 0x80 if battery > 100  else battery
                        msg =  str(deviceId) + " ba: " + str(dev.addr) + " RSSI: " + str(dev.rssi) \
                            + " Battery: " + str(battery) + " eventLoop: " + str(eventLoop) + " Ch: " + str(charging) + " " +\
                            str(dev.addr) +" " +  str(deviceId)
                        client.publish("Scanner/device", msg)
                        try:
                            data = {u'ids.bleAddress':dev.addr}
                            mainConfig.db.document(u'devices'+'/'+deviceId).update(data)
                        except:
                            pass
                        continue 
                        if battery != 0xFF:
                            charging = True if battery > 100 else False
                            battery = battery - 0x80 if battery > 100  else battery
                        try:
                            doc = db.document(u'devices' + '/' + deviceId).get()
                            doc.get(u'systemTest.stage')
                            lastContact = doc.get(u'lastPosition.timestamp')
                            msg =  str(deviceId) + " ba: " + str(dev.addr) + " RSSI: " + str(dev.rssi) \
                                + " Battery: " + str(battery) + " eventLoop: " + str(eventLoop) + " Ch: " + str(charging) +" serverContact:" + str(lastContact)
                            client.publish("Scanner/device", msg)
                        except Exception as err:
                            pass
                        
        client.publish("Scanner/log", "Awaiting commands...")
        time.sleep(mainConfig.waitTime)
        client.publish("Scanner/log", "Running commands")

        while not cls.scannerQ.empty():
            peripheral = None
            try:
                topic = cls.scannerQ.get_nowait()
                print("Scanner got in cls.scannerQ: ", topic)
                if topic in mainConfig.bleControls:
                    payload = cls.scannerQ.get()
                    arr = payload.split(" ")
                    bleAddr = arr[0]
                    try:
                        deviceId = arr[1]
                    except:
                        deviceId = "unknown"
                    comFxn.Debug("PrintDevices", "Bluetooth action on ", bleAddr, " ", deviceId)
                    try:    
                        print("doing bluetooth")
                        if fxn.doBluetooth(bleAddr, deviceId, topic, client, mainConfig.db):
                            client.publish("Scanner/log", "Done,continuing with scanner")
                        else:                    
                            client.publish("Scanner/ERROR", "BluetoothProblem")
                    except btle.BTLEDisconnectError as err:
                        print(err)
                        client.publish("Scanner/ERROR", "Bluetooth error")
                        raise cls.BluetoothError("Disconnection 4")
                    except btle.BTLEException as err:
                        print(err)  
                        client.publish("Scanner/ERROR", "Bluetooth error")
                        raise cls.BluetoothError("Disconnection 5")
                    except Exception as err:
                        print(err)
                        client.publish("Scanner/ERROR", "Bluetooth error")
                        raise cls.BluetoothError("Disconnection 6")
                        #error with doing bluetooth
                if topic == "bleControl/oad": 
                    payload = cls.scannerQ.get()
                    arr = payload.split(" ")
                    bleAddr = arr[0]
                    deviceId = arr[1]
                    msg = "Bluetooth OAD action on " + str(bleAddr) + " " + str(deviceId)
                    comFxn.Debug("PrintDevices", msg)  
                    client.publish("Scanner/log", msg)
                    try:
                        peripheral = Peripheral()
                        oad.doOad(bleAddr, deviceId, client, peripheral, mainConfig)
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
    except Exception as err:
        print(err)
        print("here3")
client.publish("Scanner/log", "Exiting")
exit()

