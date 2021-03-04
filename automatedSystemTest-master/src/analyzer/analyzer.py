import time
import datetime
import paho.mqtt.client as mqtt

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

from . import analyzerFunctions as fxn
from . import analyzerClasses as cls
from ..functions import commonFunctions as comFxn

## @analyzer
# The analyzer works on using output from the controller and the scanner, as well as getting data and settings from Firebase
# Test Settings systemTest.settings{
#   stage: current stage,
#   bletest:                    Testing bluetooth functionality
#       factoryReset:           
#           limit:                  Number of events to run
#       intervals:
#           timeLimit:              Maximum time between advertisement intervals
#       reset:
#           limit:                  Number of events to run
#       rssi:
#           limit:                  Mimimum rssi limit to pass test
#       wakeup:
#           limit:                  Number of events to run
#   sleepTest:                  Testing of sleep intervals
#       communicationDiffAcceptance: The offset to accept time between the position packet. this time goes to start up the device and send packet.
#       lightSleep:                 
#           limit:                  Number of events to run
#       deepSleep:
#           limit:                  Number of events to run
#       stayAwake:
#           limit:                  Number of events to run
#   batteryTest:                Testing battery drain
#       run:                        During running of device
#           checkTime:                  check every (seconds) if drain is ok    
#           drain:                      Drain maximum limit
#           limit:                      Number of events to run
#           time:                       sleeptime (seconds)
#       sleep:                      During sleep
#           checkTime:                  check every (seconds) if drain is ok    
#           drain:                      Drain maximum limit
#           limit:                      Number of events to run
#           time:                       sleeptime (seconds)


def RunAnalyzer(config):
    client = mqtt.Client()
    client.on_connect = fxn.onConnect
    client.on_message = fxn.onMessage
    client.connect("127.0.0.1", 1883)
    client.loop_start()

    versionMsg = "starting analyzer version " + config.analyzerVersion
    client.publish("Analyzer/log", versionMsg)
    client.subscribe("Scanner/status")
    client.subscribe("Scanner/device")

    while True:
        deviceDoc = None
        try:
            while cls.analyzerQ.empty():
                continue
            while not cls.analyzerQ.empty():
                channel = cls.analyzerQ.get()
                if channel == "Scanner/device":
                    device = cls.Device()
                    device = cls.analyzerQ.get()
                    comFxn.Debug("Analyzer ", "in scanner device", device.deviceId)
                    if device.deviceId == "00000000000000000000000000000000":
                        client.publish("Analyzer/ERROR", "zero deviceId found for " + device.bleAddr)
                        continue
                    #setting ble address in firebase
                    try:
                        deviceDoc = config.db.document(u'devices' + '/' + device.deviceId).get()
                        device.bleAddr =  deviceDoc.get(u'ids.bleAddress')
                    except:
                        config.db.document(u'devices' + '/' + device.deviceId).update({ u'ids.bleAddress' : device.bleAddr  })
                        
                    #checking stage           
                    try:
                        device.enableSystemTest = deviceDoc.get(u'config.enableSystemTest')
                        if device.enableSystemTest == False:
                            comFxn.Debug("Analyzer", "systemtest not enabled")
                            continue
                        device.currentStage = deviceDoc.get(u'systemTest.stage')
                        device.nextStage = config.nextStage[device.currentStage]
                        client.publish("Analyzer/stages", device.currentStage + " " + device.deviceId)
                        systemSettings = config.db.document(config.settingsLoc).get()
                        comFxn.Debug("Analyzer", "systemSettings found")
                        fxn.CheckStage(deviceDoc, client, device, systemSettings, config.db) 
                    except Exception as err:
                        print(err) 
                        comFxn.Debug("Analyzer", "exit StageCheck")
                        continue

                if channel == "Scanner/status":
                    try:
                        statusLog = cls.StatusLog()
                        statusLog = cls.analyzerQ.get()
                        #send log to server
                        docs = config.db.collection(u'devices')\
                            .where(u'ids.bleAddress', u'==', statusLog.bleAddr) \
                            .stream()
                        for doc in docs: 
                            msg = "Updating systemTest object " + statusLog.bleAddr + " " + doc.id
                            client.publish("Analyzer/log", msg) 
                            if statusLog.event == "bleControl/reset": #udpatimg event timestamps
                                data = {u'systemTest.bleTest.reset.timestamp': firestore.SERVER_TIMESTAMP}
                                comFxn.UpdateFirebase(doc.id, data)
                            logDoc = config.db.collection(u'devices' +'/' +doc.id + '/' + u'systemTest').add(statusLog.to_dict())
                    except Exception as err:
                        print(err)               
        except Exception as err:
            print(err)
