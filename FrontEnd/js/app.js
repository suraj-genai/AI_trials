// ========================================
// App Initialization
// ========================================

let currentDate = getTodaysDate();
let isStreaming = false;
const converter = new showdown.Converter({
  simpleLineBreaks: true,
  breaks: true,
  openLinksInNewWindow: true,
  strikethrough: true,
  tables: true
});

async function initApp() {
  // Initialize database
  await initDatabase();

  // Check for File System Access API
  if ('showSaveFilePicker' in window && !localStorage.getItem('hasFileHandle')) {
    showFileSetupPrompt();
  }

  // Load today's conversation
  await loadConversation(currentDate);

  // Setup event listeners
  setupEventListeners();
}

function setupEventListeners() {
  document.getElementById('send').addEventListener('click', handleSendMessage);
  document.getElementById('input').addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  });

  document.getElementById('export-btn').addEventListener('click', handleExport);
  document.getElementById('import-btn').addEventListener('click', handleImport);
  document.getElementById('finish-entry-btn').addEventListener('click', handleFinishEntry);
  document.getElementById('today').addEventListener('click', () => {
    currentDate = getTodaysDate();
    loadConversation(currentDate);
  });
}


// ========================================
// Message Handling
// ========================================

async function handleSendMessage() {
  if (isStreaming) return;

  const input = document.getElementById('input');
  const message = input.value.trim();

  if (!message) return;

  // Clear input
  input.value = '';

  // Save user message
  await saveMessage(currentDate, 'user', message);
  displayMessage('user', message);

  // Get conversation history
  const history = await getMessages(currentDate);

  // Stream AI response
  isStreaming = true;
  let aiResponse = '';
  const aiMessageElement = createMessageElement('assistant', '');

  try {
    const reader = await sendMessageToAI(message, history);

    for await (const chunk of streamResponse(reader)) {
      aiResponse += chunk;
      updateMessageContent(aiMessageElement, aiResponse);
      document.getElementById('messages').scrollTop = document.getElementById('messages').scrollHeight;
    }

    // Save complete AI response
    await saveMessage(currentDate, 'assistant', aiResponse);

  } catch (error) {
    console.error('Error:', error);
    aiResponse = 'Sorry, I encountered an error. Please try again.';
    updateMessageContent(aiMessageElement, aiResponse);
    await saveMessage(currentDate, 'assistant', aiResponse);
  } finally {
    isStreaming = false;
  }
}

async function loadConversation(date) {
  // Check if conversation exists
  let conversation = await getConversation(date);

  if (!conversation) {
    conversation = await createConversation(date);
  }

  // Load messages
  const messages = await getMessages(date);

  // Display messages
  const messagesContainer = document.getElementById('messages');
  messagesContainer.innerHTML = '';

  if (messages.length === 0) {
    displayMessage('assistant', "Welcome to your journal. What's on your mind today?");
  } else {
    for (const msg of messages) {
      displayMessage(msg.role, msg.content);
    }
  }
}

// ========================================
// UI Functions
// ========================================

function displayMessage(role, content) {
  const element = createMessageElement(role, content);
  const messagesContainer = document.getElementById('messages');
  messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function createMessageElement(role, content) {
  const div = document.createElement('div');
  div.className = role === 'user' ? 'flex justify-end' : 'flex justify-start';

  const bubble = document.createElement('div');
  bubble.className = role === 'user'
    ? 'bg-amber-700 text-white px-4 py-3 rounded-l-lg rounded-tr-lg max-w-lg shadow'
    : 'bg-white text-amber-900 px-4 py-3 rounded-r-lg rounded-tl-lg max-w-lg shadow border markdown-content';

  if (role === 'user') {
    bubble.textContent = content || '...';
  } else {
    bubble.innerHTML = converter.makeHtml(content || '...');
  }

  div.appendChild(bubble);
  document.getElementById('messages').appendChild(div);

  return bubble;
}

function updateMessageContent(element, content) {
  element.innerHTML = converter.makeHtml(content);
}

// ========================================
// Export/Import Handlers
// ========================================

async function handleExport() {
  try {
    await exportDatabase();
    showNotification('✅ Backup exported successfully!');
  } catch (error) {
    showNotification('❌ Export failed: ' + error.message);
  }
}

async function handleImport() {
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = '.json';

  input.onchange = async (e) => {
    try {
      const file = e.target.files[0];
      await importDatabase(file);
      showNotification('✅ Backup imported successfully!');
      location.reload();
    } catch (error) {
      showNotification('❌ Import failed: ' + error.message);
    }
  };

  input.click();
}

async function handleFinishEntry() {
  // Sync to file if available
  const synced = await syncToFile();

  if (synced) {
    showNotification('✅ Entry saved and synced to your file!');
  } else {
    // Fallback: export
    await exportDatabase();
    showNotification('✅ Entry saved and backup downloaded!');
  }
}

// ========================================
// File Setup Prompt
// ========================================

function showFileSetupPrompt() {
  const modal = document.createElement('div');
  modal.className = 'modal';
  modal.innerHTML = `
    <div class="modal-content">
      <h2>🌳 Welcome to Memory Grove!</h2>
      <p>Would you like to save your journal to a file on your computer?</p>
      <p class="small">This allows automatic syncing and backup.</p>
      <button id="setup-file-btn" class="btn-primary">Yes, setup file</button>
      <button id="skip-file-btn" class="btn-secondary">No, use browser only</button>
    </div>
  `;

  document.body.appendChild(modal);

  document.getElementById('setup-file-btn').addEventListener('click', async () => {
    const success = await setupPersistentFile();
    if (success) {
      showNotification('✅ File setup complete!');
    }
    modal.remove();
  });

  document.getElementById('skip-file-btn').addEventListener('click', () => {
    localStorage.setItem('hasFileHandle', 'skipped');
    modal.remove();
  });
}

// ========================================
// Utility Functions
// ========================================

function getTodaysDate() {
  return new Date().toISOString().split('T')[0];
}

function showNotification(message) {
  const notification = document.createElement('div');
  notification.className = 'notification';
  notification.textContent = message;
  document.body.appendChild(notification);

  setTimeout(() => notification.remove(), 3000);
}

// ========================================
// Initialize on load
// ========================================

document.addEventListener('DOMContentLoaded', initApp);