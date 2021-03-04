
Skip to content
Pull requests
Issues
Marketplace
Explore
@viggomh

1
1

    0

bikefinder/bikefinder Private
Code
Issues 0
Pull requests 0
Actions
Projects 1
Wiki
Security
Insights
Settings
bikefinder/app/modules/Bluetooth/Constants.js
@JanErikFoss JanErikFoss Prettified e8a4a71 9 days ago
executable file 100 lines (93 sloc) 3.15 KB
Code navigation is available!

Navigate your code with ease. Click on function and method calls to jump to their definitions or references in the same repository. Learn more

Code navigation is available for this repository but data for this commit does not exist.
Learn more or give us feedback
export const baseServiceTemplate = "00000000-0000-1000-8000-00805f9b34fb"
export const bikeFinderServiceTemplate = "3b940000-94a3-4b04-ab27-336173113a33"
export const oadServiceTemplate = "F000XXXX-0451-4000-B000-000000000000"

const basePrefix = baseServiceTemplate.substr(0, 4)
const basePostfix = baseServiceTemplate.substr(8)
const bfPrefix = bikeFinderServiceTemplate.substr(0, 4)
const bfPostfix = bikeFinderServiceTemplate.substr(8)
const oadPrefix = oadServiceTemplate.substr(0, 4)
const oadPostfix = oadServiceTemplate.substr(8)
const makeBase = uuid => basePrefix + uuid + basePostfix
const makeBf = uuid => bfPrefix + uuid + bfPostfix
const makeOad = uuid => oadPrefix + uuid + oadPostfix

export const deviceInformationService = "180a"
export const deviceInformationCharacteristics = {
  // These are read only
  model_number: "2a24",
  serial_number: "2a25",
  firmware_revision: "2a26",
  hardware_revision: "2a27",
  software_revision: "2a28",
  manufacturer: "2a29",
}

// export const bikeFinderServiceMinimal = "0001"
export const bikeFinderServiceMinimal = "1385"
export const bikeFinderService = makeBf(bikeFinderServiceMinimal)
export const bikeFinderCharacteristics = {
  battery_level: makeBase("2a19"),
  error_log: makeBf("1010"), // 2 bytes lang
  gps_position: makeBf("1020"), // 19 bytes lang
  gsm_position: makeBf("1021"), // 13 bytes lang
  server_data: makeBf("1050"), // 8 bytes lang
  apn: makeBf("1051"), // 20 bytes lang
  domain_name: makeBf("1052"), // 20 bytes lang
  update_interval: makeBf("1060"), // 2 bytes lang
  tap_detect_sensibility: makeBf("1070"), // 1 byte lang
  commands: makeBf("1080"), // 1 byte lang
  pin_id: makeBf("1110"), // 20 bytes lang
  new_pin: makeBf("1120"), // 20 bytes
  device_data: makeBf("1130"),
  misc_fun: makeBf("1140"),
  notify: makeBf("1150"), // 1 byte
}

export const oadServiceMinimal = "FFC0"
export const oadService = makeOad(oadServiceMinimal)
export const oadCharacteristics = {
  image_identify: makeOad("FFC1"),
  image_block: makeOad("FFC2"),
  image_count: makeOad("FFC3"),
  image_status: makeOad("FFC4"),
  image_control: makeOad("FFC5"),
}

export const DEFAULT_PIN = [0x2c, 0x28, 0x46, 0xbb, 0x5c, 0xdb, 0x87, 0xf1, 0x3d, 0xee, 0x4e, 0x8a, 0x64, 0xfb, 0x4e, 0xce, 0x65, 0x3f, 0xdb]

export const COMMANDS = {
  void: 0,
  reset: 1,
  factoryReset: 2,
  flightMode: 3,
  startAging: 4,
  errorBlinkLoop: 5,
  error: 6,
  oad: 7, // Not used on the server, only over BLE
  skipParsing: 8,
  toggleSiren: 9,
  sirenOn: 10,
  sirenOff: 11,
  installFota: 12,
  searchFota: 13,
  eraseExternalFlash: 14,
  wakeUp: 15,
  powerDown: 16,
}

export const STATUSES = {
  0x01: "status_startup",
  0x02: "status_normalSetup",
  0x03: "status_programAccelerometer",
  0x04: "status_startGetGsm",
  0x05: "status_getGsm",
  0x06: "status_sendIniPacket",
  0x07: "status_startGps",
  0x08: "status_waitForGps",
  0x09: "status_sendPosition",
  0x0a: "status_finish",
  0x0b: "status_stayAwake",
  0x0c: "status_deepSleep",
  0x0d: "status_lightSleep",
  0x10: "status_bleConnected",
  0x11: "status_airplaneMode",
  0x12: "status_oad",
  0x13: "status_fota",
  0x14: "status_mtkPowerOn",
  0x15: "status_packing",
  0x16: "status_realtime",
}

    © 2019 GitHub, Inc.
    Terms
    Privacy
    Security
    Status
    Help

    Contact GitHub
    Pricing
    API
    Training
    Blog
    About

