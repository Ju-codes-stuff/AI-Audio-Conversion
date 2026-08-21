
import asyncio
from app.database import get_async_session
from app.workers.tasks import process_audio_grievance
from sqlalchemy import text

async def test():
    async with get_async_session() as db:
        res = await db.execute(text('SELECT id FROM grievances WHERE status = ''CREATED'' ORDER BY created_at DESC LIMIT 1'))
        g_id = res.scalar()
        print('Processing ID:', g_id)

    if g_id:
        process_audio_grievance(g_id)

asyncio.run(test())

