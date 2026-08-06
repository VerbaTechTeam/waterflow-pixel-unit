from phew import logging
import myhttp
import uasyncio

async def main():
    uasyncio.create_task(myhttp.driver.run())
    myhttp.server.run()
        
uasyncio.run(main())
