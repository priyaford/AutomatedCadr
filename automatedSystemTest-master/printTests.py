import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import os
import time
import json
import datetime
from google.api_core.datetime_helpers import DatetimeWithNanoseconds
import pytz
timezone=pytz.timezone('Europe/London')
from src.config import mainConfig as mainConfig
print("Test Print to practice ")

printSystemTests = 'y'

def MakePrintTimestamp(ts):
    return str(ts.day)+'-'+str(ts.month)+' '+str(ts.hour+1)+':'+str(ts.minute)+':'+str(ts.second)

def PrintStatus(devices, db):
    try:
        for device in devices.values():
            qss = db.document('devices/'+device).get()
            batteryLevel = qss.get('battery.level')
            isCharging = qss.get('battery.isCharging')
            isChargingActive = qss.get('latestData.isChargingActive')
            adc0 = qss.get('latestData.adc0')
            adc1 = qss.get('latestData.adc1')
            imei = qss.get('ids.imei')
            iccid = qss.get('ids.iccid')
            bleAddr = qss.get('ids.bleAddress')
            versionMtk = qss.get('versions.mtkFirmware')
            versionTi = qss.get('versions.tiFirmware')
            versionBuild = qss.get('versions.buildNumber')
            subStatus = qss.get('subscription.isActive')
            try:
                latestBle = qss.get('systemTest.bleTest.intervals.latestTimestamp')
                readyForTest = qss.get('systemTest.bleTest.readyForAction')
                latestBle = MakePrintTimestamp(latestBle)
                latestServer = qss.get('latestData.battery.timestamp')
            except:
                pass
            print(device)
            print(batteryLevel, isCharging, isChargingActive, adc0, adc1, imei, iccid, bleAddr, qss.id, \
                latestBle, readyForTest, versionTi, versionBuild, versionMtk, "active:" ,subStatus, \
                "\nlatest server contact:", latestServer)
            print("")
    except Exception as err:
        print(err)
        print(device)

def InsertDeviceIdInDevices(deviceArray, config):
    i=0
    for device in deviceArray:
        if device.startswith("3521191"):
            try:
                coll = config.db.collection(u'devices') \
                    .where(u'ids.imei', "==", device) \
                    .get()
                for doc in coll:
                    print("putting ", doc.id, " instead of ", device)
                    deviceArray[i] = doc.id
                    i+=1
            except Exception as err:
                print(err)
                deviceArray[i] = ""
                i+=1

def DoYaThang(devices, config):    
    for deviceId in devices:
        print(deviceId)
        doc = config.db.document(u'devices' + '/' + deviceId).get()
        try:
            systemTest = doc.get(u'systemTest')
            for x in systemTest.keys():
                print(x, ": ", end="")
                print(systemTest[x])
            if printSystemTests == "y":
                coll = config.db.collection(u'devices' + '/' + deviceId + '/' + u'systemTest') \
                    .order_by(u'event') \
                    .stream()
                for doc in coll:    
                    event = doc.get(u'event')
                    print(event)    
            print("")
        except Exception as err:
            print(err)

DoYaThang(mainConfig.testDevices.values(), mainConfig)

PrintStatus(mainConfig.testDevices, mainConfig.db)
