from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from task_tracker_agent.config import load_settings
from task_tracker_agent.database import Database
from task_tracker_agent.services.openai_service import OpenAIService
from task_tracker_agent.ui import MainWindow


def main() -> int:
    settings = load_settings()
    db = Database(settings.database_path)
    ai = OpenAIService(settings)

    app = QApplication(sys.argv)
    window = MainWindow(db=db, ai=ai)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
