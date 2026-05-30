import math

class LocalTime:
    
    def __init__(self, h: int = 0, m: int = 0, s: int = 0, tz: int = 0):
        self.h: int = h
        self.m: int = m
        self.s: int = s
        self.tz: int = tz
    
    def set(self, h: int = 0, m: int = 0, s: int = 0):
        h = math.fabs(h) + self.tz
        if h < 0:
            h = h + 24
        self.h = int(h % 24)
        self.m = int(math.fabs(m) % 60)
        self.s = int(math.fabs(s) % 60)
        
    def timestamp(self, t=None):
        if (t is None):
            return self.h*3600 + self.m*60 + self.s
        if (t < 0):
            import time
            t = time.time()
            ts = self.timestamp(t)
            return self.timestamp(ts)
        s = int(t % 60)
        m = int(t // 60 % 60)
        h = int(t // 3600 % 24)
        self.set(h, m, s)
        return self.timestamp()
        
    def __repr__(self):
        return f'T{self.h:02d}{self.m:02d}{self.s:02d}'
    
    def timeZone(self, tz: int = None):
        if (tz is not None):
            self.tz = int(tz) % 12
        return self.tz
    
    def timeZoneRTCCorrection(self):
        import machine
        import time
        datetime = time.gmtime()
        hour = datetime[3] + self.tz
        mday = datetime[2]
        month = datetime[1]
        year = datetime[0]
        if hour < 0:
            hour = hour + 24
            mday = mday - 1;
            if mday < 1:
                month = month - 1;
                if month in (1,3,5,7,8,10,12):
                    mday = 31;
                elif month == 2:
                    if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0):
                        mday = 29
                    else:
                        mday = 28
                else:
                    mday = 30;
                
                if month < 1:
                    year = year - 1;
                    month = 12;
                    
        if hour >= 24:
            hour = hour - 24
            mday = mday + 1;
            if month in (1,3,5,7,8,10,12) and mday > 31:
                month = month + 1
                mday = mday - 31
            elif month == 2 and mday > 29:
                if year % 4 == 0 or (year % 4 == 0 and year % 100 == 0 and year % 400 != 0):
                    month = month + 1
                    mday = mday - 29
                else:
                    month = month + 1
                    mday = mday - 29
            elif mday > 30:
                month = month + 1
                mday = mday - 30
            
            if month > 12:
                year = year + 1
                month = month - 12
        
        machine.RTC().datetime((year, month, mday, hour, datetime[4], datetime[5], datetime[6], 0))
