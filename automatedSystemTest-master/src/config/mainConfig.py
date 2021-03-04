
from os import lseek
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

testServiceAccount = './src/firebase/credentials/test-service-account.json'
serviceAccount = './src/firebase/credentials/service-account.json'
currentServiceAccount = testServiceAccount


analyzerVersion = "3.0.0"

debugEnabled = True
settingsLoc = u'systemTest' + '/' + u'settings'

cred = credentials.Certificate(currentServiceAccount)
firebase_admin.initialize_app(cred)
db = firestore.client()

loopEvents = {
    1 : "startup",
    2 : "normalSetup",
    3 : "programAccerometer",
    4 : "startGetGsm",
    5 : "getGsm",
    6 : "sendIniPacket",
    7 : "startGps",
    8 : "waitForGps",
    9 : "sendPosition",
    10: "finish",
    11: "stayAwake",
    12: "deepSleep",
    13: "lightSleep",
    14: "errorEvent",
    16: "BleConnected",
    17: "airplanemode",
    18: "oadEvent",
    19: "FotaEvent",
    20: "MtkPowerOn",
}


scanTime = 5.0   #seconds
waitTime = 3


bleControls = [
    "bleControl/reset", 
    "bleControl/factoryReset",
    "bleControl/wakeup",
    "bleControl/toggleSiren",
    "Manual/reset",
    "bleControl/toggleSiren",
]

#these are the devices for entering into the test
testDevices = {
        "352119100019555" : "6b8537a19c5714b04e45bcb5586133d2",
        "352119100209321" : "5c580c35b1c83a6c648eda6baed3f74c",
        "352119100210162" : "77e3218cf22a4b007f7e48bde72026b2",
        "352119100210246" : "b722862f11aacde859f39d0ede10def7",
        "352119100210568" : "deeac4e425b830ee2c108069e2270739",
        "352119100213711" : "46d7c4e06e170cf3703dd7cf1257a995",   #no gsm
        "352119100220476" : "a41f2168e8833243bbf33e1db8dd2144",
        "352119100225582" : "5761dbc453be9cb70b148d0c41356b1a",
        "352119100243056" : "893a72f19d175988458905635451689e",
        "352119100259599" : "4ad4da572536b5362f74f87a3894bb9c",
       #protest "352119100264201" : "dd268c324a7651118a5a28f947234d24",
       # "352119100283144" : "919d90918be2d9adb71a0d9954053251"
}


#these are the users that should be added to the devices to follow the test
userArray = [
    "email|5c7ced9f012d5b66909c5ff0"
]

bleCmd = {
    "reset" : b'\x01\x00\x01\x00\x00',
    "factoryReset" : b'\x00\x00\x02\x00\x00',
    "wakeup" : b'\x00\x00\x00\x00\x00',
    "toggleSiren" : b'\x00\x00\x09\x00\x00',
    "blepin" : b'\x2C\x28\x46\xBB\x5C\xDB\x87\xF1\x3D\xEE\x4E\x8A\x64\xFB\x4E\xCE\x65\x3F\xDB\00'
}

#this is the setup for the stages the device shall go through, it will step through this based on the setup below
nextStage = {
    "systemTest/start" : "bleControl/reset",
    "bleControl/reset" : "bleControl/wakeup",
    "bleControl/wakeup" : "systemTest/lightSleepRun",
    "systemTest/lightSleepRun" : "systemTest/deepSleepRun",
    "systemTest/deepSleepRun" : "systemTest/stayAwakeRun",
    "systemTest/stayAwakeRun" : "systemTest/batteryTestRun",
    "systemTest/batteryTestRun" : "systemTest/batteryTestSleep",
    "systemTest/batteryTestSleep" : "systemTest/encryptionKey", #TODO: add accelerometer events below
    "systemTest/batteryShutdown": "systemTest/encryptionKey",
    "systemTest/lightSleepAccelerometerTest" : "accelerometerTest/deepSleepAccelerometerTest",
    "systemTest/deepSleepAccelerometerTest" : "accelerometerTest/stayAwakeAccelerometerTest",
    "systemTest/stayAwakeAccelerometerTest" : "systemTest/encryptionKey",
    "systemTest/encryptionKey" : "systemTest/encryptionKeyReset",
    "systemTest/encryptionKeyReset" : "systemTest/completed",
    "systemTest/completed" : "systemTest/completed",
    "bleControl/oad" : "bleControl/oad",
}


#these are stage options for entertest.py to set devices into.
stages = [
    "systemTest/start",
    "bleControl/reset",
    "bleControl/wakeup",
    "bleControl/oad",
    "systemTest/lightSleepRun",
    "systemTest/deepSleepRun",
    "systemTest/stayAwakeRun",
    "systemTest/batteryTestRun",
    "systemTest/batteryTestSleep",
    "systemTest/batteryShutdown",
    "systemTest/lightSleepAccelerometerTest",
    "systemTest/deepSleepAccelerometerTest",
    "systemTest/stayAwakeAccelerometerTest",
    "systemTest/encryptionKey",
    "systemTest/completed",
    "enableTest",
    "disableTest"
]

#these are the testsettings which must be set in firebase before the test is initialized and started
#systemTest(collection)->settings(document)
serverTestSettings = {
    "batteryTest": {
        "run": {
            "checkTime":600,
            "drain": 5,
            "limit":5,
            "time":1
        },
        "sleep": {
            "checkTime":20,
            "drain": 10,
            "limit":5,
            "time":5
        },
        "shutdown":{
            "limit": 5,
            "time": 3,
            "stage": "start",
            "highTemp": 70000,
            "lowTemp" : 70000,
            "normalHighTemp": 80000,
            "normalLowTemp": 300000

        }
    },
    "bleTest": {
        "factoryReset": {
            "limit":5
        },
        "intervals": {
            "timeLimit":1000
        },
        "reset": {
            "limit":20
        },
        "rssi": {
            "limit":-60
        },
        "wakeup": {
            "limit":20
        },
    },
    "encryption": {
        "key": {
            "limit":10
        },
        "keyReset": {
            "limit":10
        },
    },
    "oadTest": {
        "fromFirmware": "3.0.0",
        "includeBleStack": False,
        "limit": 50,
        "toFirmware": "2.2.5"
    },
    "sleepTest": {
        "communicationDiffAcceptance": 45,
        "deepSleep": {
            "limit":10
            },
        "lightSleep": {
            "limit":10
            },
        "stayAwake": {
            "limit":10
            },
    },
}



