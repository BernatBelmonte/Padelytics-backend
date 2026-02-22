import os
import sys
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import List, Dict
from supabase import create_client, Client

# Config
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import (
    SUPABASE_URL,
    SUPABASE_KEY,
    EMAIL_SENDER,
    EMAIL_PASSWORD,
    EMAIL_RECIPIENT,
    EMAIL_SMTP_SERVER,
    EMAIL_SMTP_PORT
)

# Collectors Imports
from scrapers.players.collector import PlayersCollector
from scrapers.tournaments.collector import TournamentsCollector
from scrapers.matches.collector import MatchesCollector


class DailyRunner:
    """
    The DailyRunner class is responsible for executing scheduled scraper tasks on a daily basis.
    It fetches tasks from the database that are scheduled for today and runs the corresponding collectors.
    """

    def __init__(self):
        """
        Initializes the DailyRunner with a Supabase client for database interactions.
        """
        self.client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        self.results: List[Dict] = []  # Store task results for email summary

    def run(self):
        """
        Main method that fetches today's scheduled tasks and executes the corresponding collectors.
        """
        print("🚀 STARTING Daily Runner")
        print("========================")
        
        today = datetime.now().strftime("%Y-%m-%d")
        print(f"📅 Today's date: {today}")
        
        tasks = self._get_todays_tasks(today)
        
        if not tasks:
            print("    ℹ️  No tasks scheduled for today.")
            return
        
        print(f"    📋 Found {len(tasks)} task(s) scheduled for today.")
        
        for task in tasks:
            task_type = task.get("task_type")
            task_id = task.get("id")
            tournament_id = task.get("tournament_id")
            
            print(f"\n    ▶️  Executing task: {task_type} (Tournament ID: {tournament_id})")
            
            try:
                self._execute_task(task_type) # type: ignore
                self._update_task_status(task_id, "completed", f"Successfully executed at {datetime.now().isoformat()}") # type: ignore
                self.results.append({"task_type": task_type, "tournament_id": tournament_id, "status": "completed", "error": None})
                print(f"    ✅ Task '{task_type}' completed successfully.")
            except Exception as e:
                error_msg = f"Error at {datetime.now().isoformat()}: {str(e)}"
                self._update_task_status(task_id, "failed", error_msg) # type: ignore
                self.results.append({"task_type": task_type, "tournament_id": tournament_id, "status": "failed", "error": str(e)})
                print(f"    ❌ Task '{task_type}' failed: {e}")

        # Send email summary
        self._send_email_summary(today)

        print("\n========================")
        print("✅ Daily Runner finished.")

    def _get_todays_tasks(self, today: str) -> List[Dict]:
        """
        Fetches all tasks scheduled for today from the database.
        
        Args:
            today: Today's date in "YYYY-MM-DD" format.
        
        Returns:
            A list of task dictionaries scheduled for today.
        """
        try:
            res = self.client.table("scraper_tasks").select("*").eq("scheduled_date", today).execute()
            return res.data or []  # type: ignore
        except Exception as e:
            print(f"    ❌ Error fetching today's tasks: {e}")
            return []

    def _execute_task(self, task_type: str) -> None:
        """
        Executes the appropriate collector based on the task type.
        
        Args:
            task_type: The type of task to execute ("players", "tournaments", or "matches").
        """
        if task_type == "players":
            PlayersCollector().start()
        elif task_type == "tournaments":
            TournamentsCollector().start()
        elif task_type == "matches":
            MatchesCollector().start()
        else:
            raise ValueError(f"Unknown task type: {task_type}")

    def _update_task_status(self, task_id: int, status: str, log: str) -> None:
        """
        Updates the task status and log in the database after execution.
        
        Args:
            task_id: The ID of the task to update.
            status: The new status of the task ("completed" or "failed").
            log: A log message describing the result of the task execution.
        """
        try:
            self.client.table("scraper_tasks").update({
                "status": status,
                "log": log,
                "executed_at": datetime.now().isoformat()
            }).eq("id", task_id).execute()
        except Exception as e:
            print(f"    ⚠️  Failed to update task status: {e}")

    def _send_email_summary(self, date: str) -> None:
        """
        Sends an email summary of the daily scraper execution.
        
        Args:
            date: The date of execution in "YYYY-MM-DD" format.
        """
        if not all([EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECIPIENT]):
            print("    ⚠️  Email credentials not configured. Skipping email notification.")
            return

        completed = [r for r in self.results if r["status"] == "completed"]
        failed = [r for r in self.results if r["status"] == "failed"]
        
        # Build email content
        subject = f"Padelytics Scraper Report - {date}"
        
        if not self.results:
            body = f"No tasks were scheduled for {date}."
        else:
            body = f"Padelytics Daily Scraper Report\n"
            body += f"================================\n"
            body += f"Date: {date}\n"
            body += f"Total Tasks: {len(self.results)}\n"
            body += f"Completed: {len(completed)}\n"
            body += f"Failed: {len(failed)}\n\n"
            
            if completed:
                body += "✅ COMPLETED TASKS:\n"
                for r in completed:
                    body += f"  - {r['task_type']} (Tournament ID: {r['tournament_id']})\n"
                body += "\n"
            
            if failed:
                body += "❌ FAILED TASKS:\n"
                for r in failed:
                    body += f"  - {r['task_type']} (Tournament ID: {r['tournament_id']})\n"
                    body += f"    Error: {r['error']}\n"

        try:
            msg = MIMEMultipart()
            msg["From"] = EMAIL_SENDER
            msg["To"] = EMAIL_RECIPIENT
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP(EMAIL_SMTP_SERVER, EMAIL_SMTP_PORT) as server:
                server.starttls()
                server.login(EMAIL_SENDER, EMAIL_PASSWORD)
                server.sendmail(EMAIL_SENDER, EMAIL_RECIPIENT, msg.as_string())
            
            print(f"    📧 Email summary sent to {EMAIL_RECIPIENT}")
        except Exception as e:
            print(f"    ❌ Failed to send email: {e}")


if __name__ == "__main__":
    runner = DailyRunner()
    runner.run()
