from waterflowpixel import WaterflowPixel
from phew import logging
from machine import Pin
from ktime import LocalTime
import time, _thread
import ujson as json
import uasyncio

class WaterflowDriver:
    
    def __init__(self):
        self._data_lock = uasyncio.Lock()
        self.offPin = Pin(20, Pin.OUT, value=0)
        self.restartCountdown = -1
        self.time = LocalTime()
        self.time.timeZoneRTCCorrection()
        self.onTime = 72000
        self.offTime = 28800
        self.timeDependency = True
        self.nol = 3
        self.waterflow = WaterflowPixel(self.nol, 0, 19)
        self.sensorPin = Pin(18, Pin.IN, Pin.PULL_UP)
        self.brightness = 255
        self.pixels = []
        self.alive = False
        self.stepTime = 1
        self.overflow = False
        self.sensorDependency = True
        self.on = True
        self.pixelProgram = 0
        self.nextPixel = (0,0,0)
        self.data = {}
        self.programs = []
        
    def __repr__(self):
        return f'WaterflowDriver with data: {json.dumps(self.data)} and with pixels: {json.dumps(self.pixels)}.'
    
    def setOperatingTime(self, start: LocalTime, end: LocalTime):
        self.onTime = start.timestamp()
        self.offTime = end.timestamp()
    
    def current_state(self):
        state = self.on
        if (self.sensorDependency and self.on):
            state = not self.sensorPin.value()
        action = "reducing"
        if (state):
            action = "extending"
        cs = {'action': action}
        cs.update(self.__dict__)
        return cs
        
    def stateAction(self, state: bool):
        if (state):
            # when active
            self.waterflow.addPixel(self.nextPixel, self.overflow)
            self.nextPixel = None
            self.offPin.value(0)
        else:
            # when inactive
            self.waterflow.removePixel()
            self.pixels = []
            if (self.waterflow.pixels == 0):
                self.offPin.value(1)
        self.waterflow.setBrightness(None, self.brightness)
        self.waterflow.showAndWait(self.stepTime)
    
    async def nextStep(self):
        state = self.on
        if self.sensorDependency and self.on:
            state = not self.sensorPin.value()
        if self.timeDependency and self.on:
            tmstmp = self.time.timestamp()
            if self.onTime < self.offTime:
                state = state and (self.onTime <= tmstmp and self.offTime >= tmstmp)
            else:
                state = state and (self.onTime >= tmstmp and self.offTime <= tmstmp)
        self.stateAction(state)
        
    async def prepareStep(self):
        import time
        self.time.timestamp(time.time())
        if (self.restartCountdown > 0):
            self.restartCountdown -= 1
            if (self.restartCountdown == 0):
                import machine
                machine.soft_reset()
        if (len(self.pixels) == 0):
            async with self._data_lock:
                try:
                    with open('data.json', 'r') as f:
                        self.data = json.load(f)
                except:
                    print("Cannot open data.json")
                if ("pixelProgram" in self.data):
                    self.pixelProgram = self.data["pixelProgram"]
                if ("brightness" in self.data):
                    self.brightness = self.data["brightness"]
                if ("stepTime" in self.data):
                    self.stepTime = self.data["stepTime"]
                if ("overflow" in self.data):
                    self.overflow = self.data["overflow"]
                if ("sensorDependency" in self.data):
                    self.sensorDependency = self.data["sensorDependency"]
                if ("timeZone" in self.data):
                    self.time.timeZone(self.data["timeZone"])
                if ("timeDependency" in self.data):
                    self.timeDependency = self.data["timeDependency"]
                if ("onTime" in self.data):
                    self.onTime = self.data["onTime"]
                if ("offTime" in self.data):
                    self.offTime = self.data["offTime"]
                if ("on" in self.data):
                    self.on = self.data["on"]
                if ("nol" in self.data):
                    self.waterflow.setNumberOfLEDs(self.data["nol"])
                try:
                    with open('pixelprograms.json', 'r') as f:
                        self.programs = json.load(f)
                except:
                    print("Cannot open pixelprograms.json")
            if self.programs and self.pixelProgram < len(self.programs):
                self.pixels = self.programs[self.pixelProgram]
            else:
                self.pixels = []
                logging.error("> Invalid pixelProgram index or empty programs list")
        if self.nextPixel is None:
            if self.pixels:
                self.nextPixel = self.pixels.pop(0)
            else:
                self.nextPixel = (0, 0, 0)  # fallback na czerń
                logging.warn("> Empty pixel program, using fallback color")
    
    async def update(self):
        await uasyncio.create_task(self.prepareStep())
        await self.nextStep()
    
    async def run(self):
        self.alive = True
        logging.info("> waterflow driver is starting...")
        Pin("LED").value(1)
        while (self.alive):
            await self.update()
        Pin("LED").value(0)
