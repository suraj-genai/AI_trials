// ========================================
// IndexedDB Setup
// ========================================

let db;

/**
 * Initialize IndexedDB database
 * Version 2: Added summaries table for AI context management
 */
async function initDatabase() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('MemoryGroveDB', 2);

    request.onerror = () => reject(request.error);
    request.onsuccess = () => {
      db = request.result;
      resolve(db);
    };

    request.onupgradeneeded = (event) => {
      const db = event.target.result;
      const oldVersion = event.oldVersion;
      const newVersion = event.newVersion;

      // Conversations store
      if (!db.objectStoreNames.contains('conversations')) {
        const conversationStore = db.createObjectStore('conversations', { keyPath: 'date' });
        conversationStore.createIndex('created_at', 'created_at', { unique: false });
      }

      // Messages store
      if (!db.objectStoreNames.contains('messages')) {
        const messageStore = db.createObjectStore('messages', { keyPath: 'id', autoIncrement: true });
        messageStore.createIndex('date', 'date', { unique: false });
        messageStore.createIndex('created_at', 'created_at', { unique: false });
      }

      // Summaries store (Version 2)
      if (!db.objectStoreNames.contains('summaries')) {
        const summaryStore = db.createObjectStore('summaries', { keyPath: 'Summary_id', autoIncrement: true });
        summaryStore.createIndex('Date', 'Date', { unique: false });
        summaryStore.createIndex('Start_id', 'Start_id', { unique: false });
        summaryStore.createIndex('End_id', 'End_id', { unique: false });
        summaryStore.createIndex('created_at', 'created_at', { unique: false });
      }
    };
  });
}

// ========================================
// Conversation Operations
// ========================================

async function createConversation(date) {
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(['conversations'], 'readwrite');
    const store = transaction.objectStore('conversations');

    const conversation = {
      date: date,
      created_at: new Date().toISOString()
    };

    const request = store.add(conversation);
    request.onsuccess = () => resolve(conversation);
    request.onerror = () => reject(request.error);
  });
}

async function getConversation(date) {
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(['conversations'], 'readonly');
    const store = transaction.objectStore('conversations');
    const request = store.get(date);

    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function getAllConversations() {
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(['conversations'], 'readonly');
    const store = transaction.objectStore('conversations');
    const request = store.getAll();

    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

/**
 * Delete a conversation for a specific date
 * @param {string} date - Date in YYYY-MM-DD format
 * @returns {Promise<void>}
 */
async function deleteConversation(date) {
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(['conversations'], 'readwrite');
    const store = transaction.objectStore('conversations');
    const request = store.delete(date);

    request.onsuccess = () => resolve();
    request.onerror = () => reject(request.error);
  });
}

// ========================================
// Message Operations
// ========================================

async function saveMessage(date, role, content) {
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(['messages'], 'readwrite');
    const store = transaction.objectStore('messages');

    const message = {
      date: date,
      role: role,
      content: content,
      created_at: new Date().toISOString()
    };

    const request = store.add(message);
    request.onsuccess = () => resolve(message);
    request.onerror = () => reject(request.error);
  });
}

async function getMessages(date) {
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(['messages'], 'readonly');
    const store = transaction.objectStore('messages');
    const index = store.index('date');
    const request = index.getAll(date);

    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function getAllMessages() {
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(['messages'], 'readonly');
    const store = transaction.objectStore('messages');
    const request = store.getAll();

    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

/**
 * Delete all messages for a specific date
 * @param {string} date - Date in YYYY-MM-DD format
 * @returns {Promise<void>}
 */
async function deleteMessagesByDate(date) {
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(['messages'], 'readwrite');
    const store = transaction.objectStore('messages');
    const index = store.index('date');
    const request = index.openCursor();

    const messagesToDelete = [];

    request.onsuccess = (e) => {
      const cursor = e.target.result;
      if (cursor) {
        if (cursor.value.date === date) {
          messagesToDelete.push(cursor.primaryKey);
        }
        cursor.continue();
      } else {
        // Delete all collected messages
        messagesToDelete.forEach(id => {
          store.delete(id);
        });
        resolve();
      }
    };

    request.onerror = () => reject(request.error);
  });
}

// ========================================
// Summary Operations
// ========================================

/**
 * Save or update a summary for a specific date
 * @param {string} date - Date in YYYY-MM-DD format
 * @param {number} startId - ID of the first message in the summary range
 * @param {number} endId - ID of the last message in the summary range
 * @param {string} summary - The summary text
 * @returns {Promise<Object>} The saved summary object
 */
async function saveSummary(date, startId, endId, summary) {
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(['summaries'], 'readwrite');
    const store = transaction.objectStore('summaries');
    const dateIndex = store.index('Date');

    // Check if summary already exists for this date
    const getRequest = dateIndex.getAll(date);
    
    getRequest.onsuccess = () => {
      const existingSummaries = getRequest.result;
      
      if (existingSummaries.length > 0) {
        // Update existing summary (should only be one per date)
        const existingSummary = existingSummaries[0];
        existingSummary.Start_id = startId;
        existingSummary.End_id = endId;
        existingSummary.Summary = summary;
        existingSummary.created_at = new Date().toISOString();

        const updateRequest = store.put(existingSummary);
        updateRequest.onsuccess = () => resolve(existingSummary);
        updateRequest.onerror = () => reject(updateRequest.error);
      } else {
        // Create new summary
        const newSummary = {
          Date: date,
          Start_id: startId,
          End_id: endId,
          Summary: summary,
          created_at: new Date().toISOString()
        };

        const addRequest = store.add(newSummary);
        addRequest.onsuccess = () => {
          newSummary.Summary_id = addRequest.result;
          resolve(newSummary);
        };
        addRequest.onerror = () => reject(addRequest.error);
      }
    };

    getRequest.onerror = () => reject(getRequest.error);
  });
}

/**
 * Get summary for a specific date
 * @param {string} date - Date in YYYY-MM-DD format
 * @returns {Promise<Object|null>} The summary object or null if not found
 */
async function getSummary(date) {
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(['summaries'], 'readonly');
    const store = transaction.objectStore('summaries');
    const dateIndex = store.index('Date');
    const request = dateIndex.getAll(date);

    request.onsuccess = () => {
      const summaries = request.result;
      // Return the most recent summary if multiple exist (shouldn't happen, but safety check)
      resolve(summaries.length > 0 ? summaries[0] : null);
    };
    request.onerror = () => reject(request.error);
  });
}

/**
 * Get all summaries
 * @returns {Promise<Array>} Array of all summary objects
 */
async function getAllSummaries() {
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(['summaries'], 'readonly');
    const store = transaction.objectStore('summaries');
    const request = store.getAll();

    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

/**
 * Delete summary for a specific date
 * @param {string} date - Date in YYYY-MM-DD format
 * @returns {Promise<void>}
 */
async function deleteSummary(date) {
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(['summaries'], 'readwrite');
    const store = transaction.objectStore('summaries');
    const dateIndex = store.index('Date');
    const request = dateIndex.getAll(date);

    request.onsuccess = () => {
      const summaries = request.result;
      if (summaries.length > 0) {
        // Delete all summaries for this date (should only be one)
        const deletePromises = summaries.map(summary => {
          return new Promise((res, rej) => {
            const deleteRequest = store.delete(summary.Summary_id);
            deleteRequest.onsuccess = () => res();
            deleteRequest.onerror = () => rej(deleteRequest.error);
          });
        });
        Promise.all(deletePromises).then(() => resolve()).catch(reject);
      } else {
        resolve();
      }
    };
    request.onerror = () => reject(request.error);
  });
}

// ========================================
// Export/Import
// ========================================

async function exportDatabase() {
  const conversations = await getAllConversations();
  const messages = await getAllMessages();
  const summaries = await getAllSummaries();

  const backup = {
    version: 2,
    exported_at: new Date().toISOString(),
    conversations: conversations,
    messages: messages,
    summaries: summaries
  };

  const blob = new Blob([JSON.stringify(backup, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);

  const a = document.createElement('a');
  a.href = url;
  a.download = `memory-grove-backup-${new Date().toISOString().split('T')[0]}.json`;
  a.click();

  URL.revokeObjectURL(url);

  return backup;
}

async function importDatabase(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();

    reader.onload = async (e) => {
      try {
        const backup = JSON.parse(e.target.result);

        // Clear existing data
        await clearDatabase();

        // Import conversations
        const convTransaction = db.transaction(['conversations'], 'readwrite');
        const convStore = convTransaction.objectStore('conversations');
        for (const conv of backup.conversations) {
          convStore.add(conv);
        }

        // Import messages
        const msgTransaction = db.transaction(['messages'], 'readwrite');
        const msgStore = msgTransaction.objectStore('messages');
        for (const msg of backup.messages) {
          msgStore.add(msg);
        }

        // Import summaries (if present - for backward compatibility)
        if (backup.summaries && backup.summaries.length > 0) {
          const summaryTransaction = db.transaction(['summaries'], 'readwrite');
          const summaryStore = summaryTransaction.objectStore('summaries');
          for (const summary of backup.summaries) {
            summaryStore.add(summary);
          }
        }

        resolve(backup);
      } catch (error) {
        reject(error);
      }
    };

    reader.onerror = () => reject(reader.error);
    reader.readAsText(file);
  });
}

async function clearDatabase() {
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(['conversations', 'messages', 'summaries'], 'readwrite');

    transaction.objectStore('conversations').clear();
    transaction.objectStore('messages').clear();
    transaction.objectStore('summaries').clear();

    transaction.oncomplete = () => resolve();
    transaction.onerror = () => reject(transaction.error);
  });
}

// ========================================
// File System Access API (Chrome/Edge)
// ========================================

let fileHandle = null;

async function setupPersistentFile() {
  if (!('showSaveFilePicker' in window)) {
    console.log('File System Access API not supported');
    return false;
  }

  try {
    fileHandle = await window.showSaveFilePicker({
      suggestedName: 'memory-grove-journal.json',
      types: [{
        description: 'Memory Grove Journal',
        accept: { 'application/json': ['.json'] }
      }]
    });

    // Save handle to IndexedDB for future sessions
    localStorage.setItem('hasFileHandle', 'true');

    return true;
  } catch (err) {
    console.log('File picker cancelled or failed:', err);
    return false;
  }
}

async function syncToFile() {
  if (!fileHandle) return false;

  try {
    const backup = await exportDatabase();

    const writable = await fileHandle.createWritable();
    await writable.write(JSON.stringify(backup, null, 2));
    await writable.close();

    console.log('✅ Synced to file');
    return true;
  } catch (err) {
    console.error('Error syncing to file:', err);
    return false;
  }
}

// Auto-sync every 30 seconds (if file handle exists)
setInterval(async () => {
  if (fileHandle) {
    await syncToFile();
  }
}, 30000);