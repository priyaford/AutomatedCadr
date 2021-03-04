from src.config import mainConfig as mainConfig


import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

devices = {
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
        #"352119100264201" : "dd268c324a7651118a5a28f947234d24",
        #"352119100283144" : "919d90918be2d9adb71a0d9954053251"
}

for device in devices.values():
    data = {
        "systemTest.bleTest.readyForAction": True
    }
    mainConfig.db.document("devices/"+device).update(data)