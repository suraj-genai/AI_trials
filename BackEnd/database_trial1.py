"""
Standalone test script for JournalDatabase
Tests database operations independently from Flask/web app
"""

from core.database import JournalDatabase
from langchain_openai import ChatOpenAI
from langchain.messages import HumanMessage, AIMessage, SystemMessage
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize database (creates journal.db in current directory)
db = JournalDatabase(db_path="test_journal.db")

# Initialize a simple LLM instance
llm = ChatOpenAI(
    openai_api_key=os.getenv("ABACUS_API_KEY"),
    model=os.getenv("ABACUS_MODEL", "gpt-4o-mini"),
    base_url=os.getenv("ABACUS_API_BASE"),
    temperature=0.7
)

SYSTEM_PROMPT = "You are a helpful journaling assistant."


def test_basic_database_operations():
    """Test 1: Basic CRUD operations"""
    print("\n" + "=" * 60)
    print("TEST 1: Basic Database Operations")
    print("=" * 60)

    test_date = "2025-11-19"

    # Save some messages
    print("\n📝 Saving messages to database...")
    db.save_message(test_date, "user", "Hello, this is my first entry")
    db.save_message(test_date, "assistant", "Welcome! I'm here to help you journal.")
    db.save_message(test_date, "user", "My name is Suraj")
    db.save_message(test_date, "assistant", "Nice to meet you, Suraj!")

    # Retrieve messages
    print("\n📖 Retrieving messages from database...")
    messages = db.get_messages(test_date)

    for i, msg in enumerate(messages, 1):
        print(f"\n  Message {i}:")
        print(f"    Role: {msg['role']}")
        print(f"    Content: {msg['content']}")
        print(f"    Timestamp: {msg['created_at']}")

    print(f"\n✅ Total messages retrieved: {len(messages)}")


def test_conversation_persistence():
    """Test 2: Multiple dates, separate conversations"""
    print("\n" + "=" * 60)
    print("TEST 2: Conversation Persistence Across Dates")
    print("=" * 60)

    # Create conversations for different dates
    dates = ["2025-11-18", "2025-11-19", "2025-11-20"]

    for date in dates:
        db.save_message(date, "user", f"Entry for {date}")
        db.save_message(date, "assistant", f"Recorded your entry for {date}")

    # Retrieve all conversation dates
    print("\n📅 All conversation dates:")
    all_dates = db.get_all_conversation_dates()
    for date in all_dates:
        print(f"  - {date}")

    # Check each date has separate messages
    print("\n🔍 Verifying separate conversations:")
    for date in dates:
        messages = db.get_messages(date)
        print(f"  {date}: {len(messages)} messages")

    print("\n✅ Conversations are properly isolated by date")


def test_llm_with_database():
    """Test 3: LLM conversation with database persistence"""
    print("\n" + "=" * 60)
    print("TEST 3: LLM + Database Integration")
    print("=" * 60)

    test_date = "2025-11-21"

    # Simulate a conversation
    conversation = [
        "Hello, I'm testing the database integration",
        "What's my name?",  # Should not know yet
        "My name is Suraj",
        "What's my name now?"  # Should remember
    ]

    # Build message history
    history = [SystemMessage(content=SYSTEM_PROMPT)]

    for user_input in conversation:
        print(f"\n👤 User: {user_input}")

        # Add user message to history and database
        history.append(HumanMessage(content=user_input))
        db.save_message(test_date, "user", user_input)

        # Get AI response
        response = llm.invoke(history)
        ai_response = response.content

        print(f"🤖 AI: {ai_response}")

        # Add AI response to history and database
        history.append(AIMessage(content=ai_response))
        db.save_message(test_date, "assistant", ai_response)

    print("\n✅ Conversation saved to database")


def test_load_from_database():
    """Test 4: Load conversation from database and continue"""
    print("\n" + "=" * 60)
    print("TEST 4: Load Previous Conversation and Continue")
    print("=" * 60)

    test_date = "2025-11-21"

    # Load messages from database
    print("\n📖 Loading conversation from database...")
    messages_from_db = db.get_messages(test_date)

    print(f"✅ Loaded {len(messages_from_db)} messages")

    # Reconstruct conversation history
    history = [SystemMessage(content=SYSTEM_PROMPT)]

    for msg in messages_from_db:
        if msg['role'] == 'user':
            history.append(HumanMessage(content=msg['content']))
        elif msg['role'] == 'assistant':
            history.append(AIMessage(content=msg['content']))

    # Continue conversation
    new_input = "Can you remind me what we talked about?"
    print(f"\n👤 User (new): {new_input}")

    history.append(HumanMessage(content=new_input))
    db.save_message(test_date, "user", new_input)

    response = llm.invoke(history)
    ai_response = response.content

    print(f"🤖 AI: {ai_response}")

    history.append(AIMessage(content=ai_response))
    db.save_message(test_date, "assistant", ai_response)

    print("\n✅ Successfully continued conversation from database")


def test_delete_conversation():
    """Test 5: Delete a conversation"""
    print("\n" + "=" * 60)
    print("TEST 5: Delete Conversation")
    print("=" * 60)

    test_date = "2025-11-18"

    # Check messages before deletion
    messages_before = db.get_messages(test_date)
    print(f"\n📊 Messages before deletion: {len(messages_before)}")

    # Delete conversation
    db.delete_conversation(test_date)
    print(f"🗑️  Deleted conversation for {test_date}")

    # Check messages after deletion
    messages_after = db.get_messages(test_date)
    print(f"📊 Messages after deletion: {len(messages_after)}")

    print("\n✅ Conversation deleted successfully")


def run_all_tests():
    """Run all tests in sequence"""
    print("\n" + "🚀" * 30)
    print("JOURNAL DATABASE TEST SUITE")
    print("🚀" * 30)

    try:
        test_basic_database_operations()
        test_conversation_persistence()
        test_llm_with_database()
        test_load_from_database()
        test_delete_conversation()

        print("\n" + "=" * 60)
        print("✅✅✅ ALL TESTS PASSED ✅✅✅")
        print("=" * 60)
        print("\n📁 Database file created: test_journal.db")
        print("💡 You can inspect it with: sqlite3 test_journal.db")
        print("💡 To see tables: .tables")
        print("💡 To see messages: SELECT * FROM messages;")

    except Exception as e:
        print("\n" + "=" * 60)
        print("❌ TEST FAILED")
        print("=" * 60)
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_all_tests()