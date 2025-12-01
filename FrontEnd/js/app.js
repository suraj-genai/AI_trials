// ========================================
// App Initialization
// ========================================

let currentDate = getTodaysDate();
let isStreaming = false;
let currentMonth = new Date().getMonth();
let currentYear = new Date().getFullYear();
let selectedDate = null;

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

  // Initialize calendar
  updateCalendar();
  updateCalendarDisplay();

  // Sync history to backend on app load
  try {
    await syncHistoryOnLoad();
  } catch (error) {
    console.error('Failed to sync history on load:', error);
    // Continue even if sync fails
  }

  // Load today's conversation
  await loadConversation(currentDate);

  // Setup event listeners
  setupEventListeners();
}

/**
 * Sync all conversation history to backend on app load
 */
async function syncHistoryOnLoad() {
  const conversations = await getAllConversations();
  const messages = await getAllMessages();
  const summaries = await getAllSummaries();

  // Send to backend
  await syncHistoryToBackend(conversations, messages, summaries);
  console.log('✅ History synced to backend');
}

// ========================================
// Event Listeners Setup
// ========================================

function setupEventListeners() {
  // Message input
  const sendBtn = document.getElementById('send');
  const input = document.getElementById('input');
  
  if (sendBtn) sendBtn.addEventListener('click', handleSendMessage);
  if (input) {
    input.addEventListener('keypress', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSendMessage();
      }
    });
    // Auto-resize textarea
    input.addEventListener('input', () => {
      input.style.height = 'auto';
      input.style.height = Math.min(input.scrollHeight, 128) + 'px';
    });
  }

  // Export/Import
  const exportBtn = document.getElementById('export-btn');
  const importBtn = document.getElementById('import-btn');
  if (exportBtn) exportBtn.addEventListener('click', handleExport);
  if (importBtn) importBtn.addEventListener('click', handleImport);

  // Finish entry
  const finishBtn = document.getElementById('finish-entry-btn');
  if (finishBtn) finishBtn.addEventListener('click', handleFinishEntry);

  // Today button (desktop and mobile)
  const todayBtn = document.getElementById('today-btn');
  const mobileTodayBtn = document.getElementById('mobile-today-btn');
  if (todayBtn) todayBtn.addEventListener('click', () => {
    currentDate = getTodaysDate();
    selectedDate = null;
    loadConversation(currentDate);
    updateCalendar();
    updateButtonStates();
  });
  if (mobileTodayBtn) mobileTodayBtn.addEventListener('click', () => {
    currentDate = getTodaysDate();
    selectedDate = null;
    loadConversation(currentDate);
    updateCalendar();
    updateButtonStates();
    closeMobileCalendar();
  });

  // Calendar navigation
  const prevMonth = document.getElementById('prev-month');
  const nextMonth = document.getElementById('next-month');
  const mobilePrevMonth = document.getElementById('mobile-prev-month');
  const mobileNextMonth = document.getElementById('mobile-next-month');
  
  if (prevMonth) prevMonth.addEventListener('click', () => navigateMonth(-1));
  if (nextMonth) nextMonth.addEventListener('click', () => navigateMonth(1));
  if (mobilePrevMonth) mobilePrevMonth.addEventListener('click', () => navigateMonth(-1));
  if (mobileNextMonth) mobileNextMonth.addEventListener('click', () => navigateMonth(1));

  // Make entry button
  const makeEntryBtn = document.getElementById('make-entry-btn');
  const mobileMakeEntryBtn = document.getElementById('mobile-make-entry-btn');
  if (makeEntryBtn) makeEntryBtn.addEventListener('click', handleMakeEntry);
  if (mobileMakeEntryBtn) mobileMakeEntryBtn.addEventListener('click', () => {
    handleMakeEntry();
    closeMobileCalendar();
  });

  // Delete entry button
  const deleteEntryBtn = document.getElementById('delete-entry-btn');
  const mobileDeleteEntryBtn = document.getElementById('mobile-delete-entry-btn');
  if (deleteEntryBtn) deleteEntryBtn.addEventListener('click', handleDeleteEntry);
  if (mobileDeleteEntryBtn) mobileDeleteEntryBtn.addEventListener('click', () => {
    handleDeleteEntry();
    closeMobileCalendar();
  });

  // Mobile calendar toggle
  const mobileCalendarToggle = document.getElementById('mobile-calendar-toggle');
  const closeMobileCalendarBtn = document.getElementById('close-mobile-calendar');
  if (mobileCalendarToggle) mobileCalendarToggle.addEventListener('click', openMobileCalendar);
  if (closeMobileCalendarBtn) closeMobileCalendarBtn.addEventListener('click', closeMobileCalendar);

  // Settings modal
  const settingsBtn = document.getElementById('settings-btn');
  const closeSettingsBtn = document.getElementById('close-settings-btn');
  if (settingsBtn) settingsBtn.addEventListener('click', openSettings);
  if (closeSettingsBtn) closeSettingsBtn.addEventListener('click', closeSettings);

  // Close modals on backdrop click
  const settingsModal = document.getElementById('settings-modal');
  const mobileCalendarModal = document.getElementById('mobile-calendar-modal');
  if (settingsModal) {
    settingsModal.addEventListener('click', (e) => {
      if (e.target === settingsModal) closeSettings();
    });
  }
  if (mobileCalendarModal) {
    mobileCalendarModal.addEventListener('click', (e) => {
      if (e.target === mobileCalendarModal) closeMobileCalendar();
    });
  }
}

// ========================================
// Calendar Functions
// ========================================

function updateCalendarDisplay() {
  const monthNames = ['January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'];
  
  const currentMonthEl = document.getElementById('current-month');
  const mobileCurrentMonthEl = document.getElementById('mobile-current-month');
  
  if (currentMonthEl) {
    currentMonthEl.textContent = `${monthNames[currentMonth]} ${currentYear}`;
  }
  if (mobileCurrentMonthEl) {
    mobileCurrentMonthEl.textContent = `${monthNames[currentMonth]} ${currentYear}`;
  }
}

function navigateMonth(direction) {
  currentMonth += direction;
  if (currentMonth < 0) {
    currentMonth = 11;
    currentYear--;
  } else if (currentMonth > 11) {
    currentMonth = 0;
    currentYear++;
  }
  updateCalendar();
  updateCalendarDisplay();
}

async function updateCalendar() {
  const calendarEl = document.getElementById('calendar');
  const mobileCalendarEl = document.getElementById('mobile-calendar');
  
  if (!calendarEl && !mobileCalendarEl) return;

  const firstDay = new Date(currentYear, currentMonth, 1).getDay();
  const daysInMonth = new Date(currentYear, currentMonth + 1, 0).getDate();
  const today = new Date();
  const isCurrentMonth = today.getMonth() === currentMonth && today.getFullYear() === currentYear;
  const todayDate = today.getDate();

  // Get all conversations to mark dates
  const conversations = await getAllConversations();
  const conversationDates = new Set(conversations.map(c => c.date));

  const generateCalendarHTML = () => {
    let html = '';
    
    // Empty cells for days before month starts
    for (let i = 0; i < firstDay; i++) {
      html += '<div class="text-gray-400"></div>';
    }

    // Days of the month
    for (let day = 1; day <= daysInMonth; day++) {
      const dateStr = `${currentYear}-${String(currentMonth + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
      const isToday = isCurrentMonth && day === todayDate;
      const hasEntry = conversationDates.has(dateStr);
      const isSelected = selectedDate === dateStr;
      const isCurrentDate = currentDate === dateStr;

      let classes = 'cursor-pointer hover:bg-amber-100 rounded-full w-8 h-8 leading-8 mx-auto transition';
      
      if (isToday) {
        classes += ' bg-amber-600 text-white font-bold';
      } else if (isSelected || isCurrentDate) {
        classes += ' bg-amber-400 text-white font-semibold';
      } else if (hasEntry) {
        classes += ' bg-amber-200 text-amber-900';
      } else {
        classes += ' text-amber-900';
      }

      html += `<div class="${classes}" data-date="${dateStr}">${day}</div>`;
    }

    return html;
  };

  if (calendarEl) {
    calendarEl.innerHTML = generateCalendarHTML();
    // Add click listeners
    calendarEl.querySelectorAll('[data-date]').forEach(el => {
      el.addEventListener('click', () => {
        const date = el.getAttribute('data-date');
        selectedDate = date;
        currentDate = date;
        loadConversation(date);
        updateCalendar();
        updateButtonStates();
      });
    });
  }

  if (mobileCalendarEl) {
    mobileCalendarEl.innerHTML = generateCalendarHTML();
    // Add click listeners
    mobileCalendarEl.querySelectorAll('[data-date]').forEach(el => {
      el.addEventListener('click', () => {
        const date = el.getAttribute('data-date');
        selectedDate = date;
        currentDate = date;
        loadConversation(date);
        updateCalendar();
        updateButtonStates();
        closeMobileCalendar();
      });
    });
  }
}

function updateButtonStates() {
  const makeEntryBtn = document.getElementById('make-entry-btn');
  const mobileMakeEntryBtn = document.getElementById('mobile-make-entry-btn');
  const deleteEntryBtn = document.getElementById('delete-entry-btn');
  const mobileDeleteEntryBtn = document.getElementById('mobile-delete-entry-btn');

  getConversation(currentDate).then(conv => {
    const hasEntry = conv !== undefined && conv !== null;
    
    if (makeEntryBtn) makeEntryBtn.disabled = hasEntry;
    if (mobileMakeEntryBtn) mobileMakeEntryBtn.disabled = hasEntry;
    if (deleteEntryBtn) deleteEntryBtn.disabled = !hasEntry;
    if (mobileDeleteEntryBtn) mobileDeleteEntryBtn.disabled = !hasEntry;
  });
}

// ========================================
// Modal Functions
// ========================================

function openMobileCalendar() {
  const modal = document.getElementById('mobile-calendar-modal');
  if (modal) {
    modal.classList.remove('hidden');
    updateCalendar(); // Refresh calendar in modal
  }
}

function closeMobileCalendar() {
  const modal = document.getElementById('mobile-calendar-modal');
  if (modal) modal.classList.add('hidden');
}

function openSettings() {
  const modal = document.getElementById('settings-modal');
  if (modal) modal.classList.remove('hidden');
}

function closeSettings() {
  const modal = document.getElementById('settings-modal');
  if (modal) modal.classList.add('hidden');
}

// ========================================
// Message Handling
// ========================================

async function handleSendMessage() {
  if (isStreaming) return;
  const input = document.getElementById('input');
  const message = input.value.trim();
  if (!message) return;

  input.value = '';
  input.style.height = 'auto';

  await saveMessage(currentDate, 'user', message);
  displayMessage('user', message);

  const history = await getMessages(currentDate);

  // --- NEW LOGIC START ---
  // Fetch the most recent summary (Long Term Memory)
  const allSummaries = await getAllSummaries();
  // Sort by date descending (newest first)
  allSummaries.sort((a, b) => new Date(b.Date) - new Date(a.Date));

  let context = "";
  if (allSummaries.length > 0) {
    // We use the MOST RECENT summary as context
    context = allSummaries[0].Summary;
  }
  // --- NEW LOGIC END ---

  isStreaming = true;
  let aiResponse = '';
  const aiMessageElement = createMessageElement('assistant', '');

  try {
    // Pass context to API
    const reader = await sendMessageToAI(message, history, currentDate, context);

    for await (const chunk of streamResponse(reader)) {
      aiResponse += chunk;
      updateMessageContent(aiMessageElement, aiResponse);
      const messagesContainer = document.getElementById('messages');
      if (messagesContainer) messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
    updateMessageContent(aiMessageElement, aiResponse);
    await saveMessage(currentDate, 'assistant', aiResponse);

  } catch (error) {
    console.error('Error:', error);
    aiResponse = 'Sorry, I encountered an error.';
    updateMessageContent(aiMessageElement, aiResponse);
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
  if (!messagesContainer) return;

  messagesContainer.innerHTML = '';

  if (messages.length === 0) {
    displayMessage('assistant', "Welcome to your journal. What's on your mind today?");
  } else {
    for (const msg of messages) {
      displayMessage(msg.role, msg.content);
    }
  }

  // Update button states
  updateButtonStates();
  
  // Scroll to bottom
  setTimeout(() => {
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  }, 100);
}

// ========================================
// Entry Management
// ========================================

async function handleMakeEntry() {
  if (selectedDate) {
    currentDate = selectedDate;
  } else {
    currentDate = getTodaysDate();
  }
  
  await loadConversation(currentDate);
  updateButtonStates();
  
  // Focus on input
  const input = document.getElementById('input');
  if (input) input.focus();
}

async function handleDeleteEntry() {
  if (!confirm('Are you sure you want to delete this entry? This action cannot be undone.')) {
    return;
  }

  try {
    // Delete all messages for this date
    await deleteMessagesByDate(currentDate);
    
    // Delete conversation
    await deleteConversation(currentDate);
    
    // Delete summary if exists
    await deleteSummary(currentDate);

    // Clear the messages container
    const messagesContainer = document.getElementById('messages');
    if (messagesContainer) {
      messagesContainer.innerHTML = '';
      displayMessage('assistant', "Entry deleted. Start a new entry whenever you're ready.");
    }

    // Refresh calendar and button states
    updateCalendar();
    updateButtonStates();
    showNotification('✅ Entry deleted successfully');
  } catch (error) {
    console.error('Error deleting entry:', error);
    showNotification('❌ Failed to delete entry');
  }
}

// ========================================
// UI Functions
// ========================================

function displayMessage(role, content) {
  const element = createMessageElement(role, content);
  const messagesContainer = document.getElementById('messages');
  if (messagesContainer) {
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  }
}

/**
 * Create a message element with proper formatting
 * @param {string} role - 'user' or 'assistant'
 * @param {string} content - Message content
 * @returns {HTMLElement} The message bubble element
 */
function createMessageElement(role, content) {
  const div = document.createElement('div');
  div.className = role === 'user' ? 'flex justify-end mb-4' : 'flex justify-start mb-4';

  const bubble = document.createElement('div');
  bubble.className = role === 'user'
    ? 'bg-amber-700 text-white px-4 py-3 rounded-l-lg rounded-tr-lg max-w-lg shadow user-message-content'
    : 'bg-white text-amber-900 px-4 py-3 rounded-r-lg rounded-tl-lg max-w-lg shadow border markdown-content';

  if (role === 'user') {
    // For user messages: preserve formatting (newlines, spacing) but don't render markdown
    bubble.innerHTML = formatUserMessage(content || '...');
  } else {
    // For assistant messages: render markdown
    bubble.innerHTML = converter.makeHtml(content || '...');
  }

  div.appendChild(bubble);
  const messagesContainer = document.getElementById('messages');
  if (messagesContainer) {
    messagesContainer.appendChild(div);
  }

  return bubble;
}

/**
 * Format user message to preserve newlines and spacing
 * Converts newlines to <br> and preserves spacing
 * @param {string} text - Raw text input
 * @returns {string} HTML formatted text
 */
function formatUserMessage(text) {
  if (!text) return '';
  
  // Escape HTML to prevent XSS
  const escaped = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
  
  // Convert newlines to <br>
  return escaped.replace(/\n/g, '<br>');
}

/**
 * Update message content with proper formatting
 * @param {HTMLElement} element - The message bubble element
 * @param {string} content - New content to display
 */
function updateMessageContent(element, content) {
  if (!element) return;
  
  // Check if it's a user message or assistant message
  const isUserMessage = element.classList.contains('user-message-content');
  
  if (isUserMessage) {
    // For user messages: preserve formatting
    element.innerHTML = formatUserMessage(content);
  } else {
    // For assistant messages: render markdown
    element.innerHTML = converter.makeHtml(content);
  }
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
  if (isStreaming) {
    showNotification('⏳ Please wait for the AI to finish responding');
    return;
  }

  try {
    const finishBtn = document.getElementById('finish-entry-btn');
    if (finishBtn) {
      finishBtn.disabled = true;
      finishBtn.textContent = '⏳ Memorizing...'; // Changed text
    }

    // 1. Get Today's Messages
    const messages = await getMessages(currentDate);
    if (messages.length === 0) {
      showNotification('ℹ️ No messages to summarize');
      if (finishBtn) {
          finishBtn.disabled = false;
          finishBtn.textContent = '✅ Finish';
      }
      return;
    }

    // 2. Convert messages to a single text block
    const chatText = messages.map(m => `${m.role}: ${m.content}`).join('\n');

    // 3. Get Previous Summary (The one before today)
    const allSummaries = await getAllSummaries();
    // Filter out ANY summary that might already exist for TODAY (to avoid self-referencing if clicked twice)
    const pastSummaries = allSummaries.filter(s => s.Date !== currentDate);
    // Sort descending
    pastSummaries.sort((a, b) => new Date(b.Date) - new Date(a.Date));

    const prevSummary = pastSummaries.length > 0 ? pastSummaries[0].Summary : "";

    // 4. Request New Summary (Recursive)
    // Note: We are now expecting a JSON response, not a stream, per the Python change
    const summaryData = await requestSummarization(currentDate, chatText, prevSummary);

    // 5. Save logic remains similar
    if (summaryData && summaryData.summary) {
      const startId = messages[0].id;
      const endId = messages[messages.length - 1].id;

      await saveSummary(currentDate, startId, endId, summaryData.summary);
      showNotification('✅ Memory updated successfully!');

      // Optional: Display the new memory summary in the chat?
      // displayMessage('system', "💾 Memory Updated: " + summaryData.summary);
    }

    // Sync to file if available
    const synced = await syncToFile();
    if (synced) {
      console.log('✅ Synced to file');
    }
  }  catch (error) {
    console.error('Error finishing entry:', error);
    showNotification('❌ Failed: ' + error.message);
  } finally {
    const finishBtn = document.getElementById('finish-entry-btn');
    if (finishBtn) {
      finishBtn.disabled = false;
      finishBtn.textContent = '✅ Finish';
    }
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
