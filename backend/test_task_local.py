
from app.database import SessionLocal
from app.workers.tasks import process_audio_grievance
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)

with SessionLocal() as db:
    res = db.execute(text('SELECT id FROM grievances ORDER BY created_at DESC LIMIT 1'))
    g_id = res.scalar()
    print('Processing ID:', g_id)
    if g_id:
        process_audio_grievance(str(g_id))

