import evdev
from evdev import *
from azure.storage.queue import QueueService, QueueMessageFormat
import threading
import time
from queue import *
import datetime

# responsible for uploading the barcodes to the azure storage queue.
class BarcodeUploader:
  def __init__(self):
    # Instiantiate the azure queue service (from the azure.storage.queue package)
    self.queue_service = QueueService(account_name='wereoutof', account_key='your-key-here')

    # azure functions is _very_ confused is the text isn't base64 encoded
    self.queue_service.encode_function = QueueMessageFormat.text_base64encode

    # use a simple queue to avoid blocking operations
    self.queue = LifoQueue()
    t = threading.Thread(target=self.worker, args=())
    t.daemon = True
    t.start()

  # processes all messages (barcodes) in queue - uploading them to azure one by one
  def worker(self):
      while True:
        while not self.queue.empty():
          try:
            barcode = self.queue.get()
            self.queue_service.put_message('barcodes', u'account-key:' + barcode)
          except Exception as exc:
            print("Exception occured when uploading barcode:"  + repr(exc))
            # re-submit task into queue
            self.queue.task_done()
            self.queue.put(barcode)
          else:
            print("Barcode " + barcode + " registered")
            self.queue.task_done()
        time.sleep(1)

  def register(self, barcode):
      print "Registering barcode " + barcode + "..."
      self.queue.put(barcode)

current_barcode = ""

# Reads barcode from "device"
def readBarcodes():
  global current_barcode
  print ("Reading barcodes from device")
  for event in device.read_loop():
    if event.type == evdev.ecodes.EV_KEY and event.value == 1:
      keycode = categorize(event).keycode
      if keycode == 'KEY_ENTER':
        uploader.register(current_barcode)
        current_barcode = ""
      else:
        current_barcode += keycode[4:]

# Finds the input device with the name "Barcode Reader ".
# Could and should be parameterized, of course. Device name as cmd line parameter, perhaps?
def find_device():
  device_name = 'Barcode Reader '
  devices = [evdev.InputDevice(fn) for fn in evdev.list_devices()]
  for d in devices:
    if d.name == device_name:
      print("Found device " + d.name)
      device = d
  return device

# Find device...
device = find_device()
if device is None:
  print("Unable to find " + device_name)
else:
  #... instantiate the uploader...
  uploader = BarcodeUploader()
  # ... and read the bar codes.
  readBarcodes()
