import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))

from app.database.session import session_scope
from app.database.models import Project, ActivityEvent
from sqlalchemy import select, delete

def main():
    with session_scope() as session:
        project = session.scalar(select(Project).where(Project.key == "SMOKE"))
        if project:
            print(f"Found project {project.id} with key SMOKE, deleting related activity events...")
            session.execute(delete(ActivityEvent).where(ActivityEvent.project_id == project.id))
            print("Deleting project...")
            session.delete(project)
            session.commit()
            print("Deleted successfully!")
        else:
            print("SMOKE project not found.")

if __name__ == "__main__":
    main()
