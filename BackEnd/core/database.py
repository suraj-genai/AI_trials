import sqlite3
from datetime import datetime
from typing import List, Dict, Optional
import os


class JournalDatabase:
    """SQLite database manager for journal conversations"""

    def __init__(self, db_path: str = "journal.db"):
        self.db_path = db_path
        self.init_database()

    def get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Return rows as dictionaries
        return conn

    def init_database(self):
        """Initialize database schema"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Conversations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Messages table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                token_count INTEGER,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id)
            )
        """)

        # Metadata table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                key TEXT NOT NULL,
                value TEXT,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id)
            )
        """)

        conn.commit()
        conn.close()
        print("✅ Database initialized")

    def get_or_create_conversation(self, date: str) -> int:
        """Get conversation ID for a date, create if doesn't exist"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Try to get existing conversation
        cursor.execute("SELECT id FROM conversations WHERE date = ?", (date,))
        row = cursor.fetchone()

        if row:
            conversation_id = row['id']
        else:
            # Create new conversation
            cursor.execute(
                "INSERT INTO conversations (date) VALUES (?)",
                (date,)
            )
            conversation_id = cursor.lastrowid
            conn.commit()

        conn.close()
        return conversation_id

    def save_message(self, date: str, role: str, content: str, token_count: Optional[int] = None):
        """Save a message to the database"""
        conversation_id = self.get_or_create_conversation(date)

        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO messages (conversation_id, role, content, token_count)
            VALUES (?, ?, ?, ?)
            """,
            (conversation_id, role, content, token_count)
        )

        # Update conversation timestamp
        cursor.execute(
            "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (conversation_id,)
        )

        conn.commit()
        conn.close()

    def get_messages(self, date: str) -> List[Dict]:
        """Get all messages for a specific date"""
        conversation_id = self.get_or_create_conversation(date)

        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT role, content, created_at, token_count
            FROM messages
            WHERE conversation_id = ?
            ORDER BY created_at ASC
            """,
            (conversation_id,)
        )

        messages = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return messages

    def get_all_conversation_dates(self) -> List[str]:
        """Get all dates that have conversations"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT date FROM conversations ORDER BY date DESC"
        )

        dates = [row['date'] for row in cursor.fetchall()]
        conn.close()

        return dates

    def delete_conversation(self, date: str):
        """Delete a conversation and all its messages"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM conversations WHERE date = ?", (date,))
        row = cursor.fetchone()

        if row:
            conversation_id = row['id']
            cursor.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
            cursor.execute("DELETE FROM metadata WHERE conversation_id = ?", (conversation_id,))
            cursor.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
            conn.commit()

        conn.close()


# Create singleton instance
db = JournalDatabase()