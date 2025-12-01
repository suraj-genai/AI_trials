// ========================================
// API Configuration
// ========================================

const API_BASE_URL = window.location.origin;

// ========================================
// Chat API
// ========================================

/**
 * Send message to AI via Flask backend
 * @param {string} message - User's message
 * @param {Array} history - Conversation history (full message objects with id, date, role, content, created_at)
 * @param {string} date - Current date in YYYY-MM-DD format
 * @returns {Promise<ReadableStreamDefaultReader>} Stream reader for SSE response
 */
async function sendMessageToAI(message, history, date, context) {
  // Added 'context' parameter
  const response = await fetch(`${API_BASE_URL}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message: message,
      history: history,
      date: date,
      context: context // Send the long-term memory
    })
  });

  if (!response.ok) throw new Error(`API error: ${response.status}`);
  return response.body.getReader();
}

async function requestSummarization(date, chatText, prevSummary) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/summarize`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        date: date,
        chat_text: chatText,
        previous_summary: prevSummary
      })
    });

    if (!response.ok) {
      throw new Error(`Summarization failed: ${response.status}`);
    }

    // Backend returns standard JSON, not a stream
    const data = await response.json();
    return data;

  } catch (error) {
    console.error('Error requesting summarization:', error);
    throw error;
  }
}

// ========================================
// Stream Handler
// ========================================

/**
 * Stream response handler for Server-Sent Events (SSE)
 * Parses JSON packets from backend and yields content chunks
 * @param {ReadableStreamDefaultReader} reader - Stream reader
 * @yields {string} Content chunks from the stream
 */
async function* streamResponse(reader) {
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();

    if (done) {
      // Process any remaining buffer
      if (buffer.trim()) {
        const chunks = processBuffer(buffer);
        for (const chunk of chunks) {
          if (chunk) yield chunk;
        }
      }
      break;
    }

    // Decode chunk and add to buffer
    buffer += decoder.decode(value, { stream: true });
    
    // Process complete SSE messages (ending with \n\n)
    const lines = buffer.split('\n\n');
    
    // Keep the last incomplete line in buffer
    buffer = lines.pop() || '';

    // Process complete messages
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.slice(6).trim();

        if (data === '[DONE]' || data === '') {
          continue;
        }

        try {
          const parsed = JSON.parse(data);
          
          // Handle different packet types
          if (parsed.content !== undefined) {
            // Content packet: {"content": "text chunk"}
            yield parsed.content;
          } else if (parsed.done === true) {
            // Done packet: {"done": true}
            return;
          } else if (parsed.error) {
            // Error packet: {"error": "error message"}
            throw new Error(parsed.error);
          } else if (typeof parsed === 'string') {
            // Fallback: if backend sends raw string, use it
            yield parsed;
          }
        } catch (e) {
          // If JSON parsing fails, try to extract content as string
          if (data && data !== '[DONE]') {
            console.warn('Failed to parse JSON, using raw data:', e);
            yield data;
          }
        }
      }
    }
  }
}

/**
 * Process remaining buffer for any incomplete messages
 * @param {string} buffer - Remaining buffer content
 * @returns {Array<string>} Array of content chunks
 */
function processBuffer(buffer) {
  const chunks = [];
  const lines = buffer.split('\n');
  
  for (const line of lines) {
    if (line.startsWith('data: ')) {
      const data = line.slice(6).trim();
      if (data && data !== '[DONE]') {
        try {
          const parsed = JSON.parse(data);
          if (parsed.content !== undefined) {
            chunks.push(parsed.content);
          }
        } catch (e) {
          // If parsing fails, use raw data
          if (data) chunks.push(data);
        }
      }
    }
  }
  
  return chunks;
}

// ========================================
// Sync API
// ========================================

/**
 * Sync all conversation history and summaries to backend
 * Called on app load to give backend context
 * @param {Array} conversations - All conversations from IndexedDB
 * @param {Array} messages - All messages from IndexedDB
 * @param {Array} summaries - All summaries from IndexedDB
 * @returns {Promise<Object>} Response from backend
 */
async function syncHistoryToBackend(conversations, messages, summaries) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/sync`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        conversations: conversations || [],
        messages: messages || [],
        summaries: summaries || []
      })
    });

    if (!response.ok) {
      throw new Error(`Sync failed: ${response.status}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Error syncing to backend:', error);
    throw error;
  }
}

