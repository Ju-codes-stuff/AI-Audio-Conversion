
import asyncio
from app.database import engine
from sqlalchemy import text

async def check_col():
    async with engine.connect() as conn:
        res = await conn.execute(text('SELECT data_type, udt_name FROM information_schema.columns WHERE table_name = ''grievances'' AND column_name = ''status'''))
        print(res.all())

asyncio.run(check_col())

