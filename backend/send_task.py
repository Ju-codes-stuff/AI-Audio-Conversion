
import asyncio
from app.database import engine
from sqlalchemy import text
from app.workers.tasks import process_audio_grievance

async def test():
    async with engine.connect() as conn:
        res = await conn.execute(text('SELECT id FROM grievances WHERE status = \'CREATED\' ORDER BY created_at DESC LIMIT 1'))
        g_id = res.scalar()
        if g_id:
            print('Sending task for:', g_id)
            process_audio_grievance.delay(str(g_id))

asyncio.run(test())

