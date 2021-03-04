import time
import datetime
import paho.mqtt.client as mqtt
from multiprocessing import Queue


q = Queue()

filename = str(time.strftime("%Y%m%d-%H%M%S"))+".log"

def onMessage(client, userdata, msg):
    try:
        data = {"topic": msg.topic, "payload": msg.payload}
        q.put(data)   
    except Exception as err:
        print(err)

def onConnect(client, userdata, flags, rc):
    print("Connected Logger to mqtt with result code "+str(rc))
    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    client.subscribe("Scanner/#")
    client.subscribe("Controller/#")
    client.subscribe("Analyzer/#")

client = mqtt.Client()
client.on_connect = onConnect
client.on_message = onMessage
client.connect("127.0.0.1", 1883)
client.loop_start()

client.publish("Logger/log", "starting Logger")

def RunMqttLogger():
    while True: 
        try:   
            if not q.empty():
                msg = q.get()
                print(str(datetime.datetime.now()) + " " + str(msg["topic"]) + " " + str(msg["payload"]))
                with open(filename,'a') as f:
                    f.write(str(datetime.datetime.now()) + " " + str(msg["topic"]) + " " + str(msg["payload"]) + "\n")
        except Exception as err:
            print(err)