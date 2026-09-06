"""
utils/scheduler.py
--------------------
Daily background job: publishes any posts whose `scheduled_date` has
arrived, for every workspace. Import and call `start_scheduler()` once
from app.py (guard against Streamlit's re-run behavior re-registering
the job -- see note in app.py).
"""

import os
import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

from utils.database import Database
from utils.linkedin_publisher import LinkedInAPI, LinkedInAPIError

logger = logging.getLogger("scheduler")
_scheduler = None


def _publish_due_posts():
    db = Database()
    today = datetime.utcnow().date().isoformat()
    for ws in db.get_workspaces():
        token = ws.get("linkedin_access_token") or os.getenv("LINKEDIN_ACCESS_TOKEN")
        if not token:
            continue
        due_posts = [
            p for p in db.get_posts(ws["id"], status="scheduled")
            if p.get("scheduled_date") and p["scheduled_date"] <= today
        ]
        if not due_posts:
            continue
        try:
            api = LinkedInAPI(access_token=token)
            author_urn = ws.get("linkedin_person_urn") or api.get_person_urn()
        except (LinkedInAPIError, ValueError) as e:
            logger.warning(f"Skipping workspace {ws['id']} publish: {e}")
            continue

        for post in due_posts:
            try:
                urn = api.publish_post(post["content"], author_urn=author_urn)
                db.mark_published(post["id"], ws["id"], urn)
                logger.info(f"Published post {post['id']} for workspace {ws['id']}")
            except LinkedInAPIError as e:
                logger.error(f"Failed to publish post {post['id']}: {e}")


def start_scheduler(hour: int = 8, minute: int = 0):
    global _scheduler
    if _scheduler is not None:
        return _scheduler  # already running -- avoid double-registering in Streamlit reruns

    _scheduler = BackgroundScheduler()
    _scheduler.add_job(_publish_due_posts, "cron", hour=hour, minute=minute, id="publish_due_posts")
    _scheduler.start()
    logger.info(f"Scheduler started -- daily publish job at {hour:02d}:{minute:02d} UTC")
    return _scheduler
