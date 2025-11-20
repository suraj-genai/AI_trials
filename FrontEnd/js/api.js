// ========================================
// API Configuration
// ========================================

const API_BASE_URL = window.location.origin;

// ========================================
// Chat API
// ========================================

async function sendMessageToAI(message, history) {
  const response = await fetch(`${API_BASE_URL}/api/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      message: message,
      history: history
    })
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }

  return response.body.getReader();
}

// ========================================
// Stream Handler
// ========================================

async function* streamResponse(reader) {
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();

    if (done) break;

    const chunk = decoder.decode(value);
    const lines = chunk.split('\n\n');

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.slice(6);

        if (data === '[DONE]') {
          return;
        }

        try {
          const parsed = JSON.parse(data);
          if (parsed.content) {
            yield parsed.content;
          } else if (parsed.error) {
            throw new Error(parsed.error);
          }
        } catch (e) {
          console.error('Parse error:', e);
        }
      }
    }
  }
}