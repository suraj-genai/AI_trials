# Memory Grove – Privacy-First AI Journal

Memory Grove is a conversational AI journaling application designed to help users reflect on their daily thoughts while maintaining complete control over their data.

## Live Demo
Access the deployed application here:  
https://lnkd.in/g3aFnYtw  

*Note: If the Space is inactive, you may need to trigger a restart. The environment will reinstall dependencies and may take a short time to become available.*

## Key Features
- **Conversational Journaling:** Interactive AI chatbot that guides users through daily reflections.
- **Persistent Memory:** Maintains context across multiple sessions for more meaningful interactions.
- **Daily Summarization:** Automatically generates summaries to retain long-term context efficiently.
- **Privacy-First Design:** User data is stored locally (IndexedDB), ensuring full ownership and control.
- **Data Export:** Users can download their conversation history as a JSON file for portability and personal analysis.

## Tech Stack
- **Backend:** Python, LangChain  
- **Frontend:** JavaScript (IndexedDB for local storage)  
- **Deployment:** Hugging Face Spaces  

## Architecture Overview
- Backend handles AI interaction and prompt workflows  
- Frontend manages user interaction and local data persistence  
- Summarization layer maintains context across sessions  

## Local Setup (Optional)

To run locally:

1. Clone the repository  
2. Install dependencies  
3. Create a `.env` file and add your OpenAI API key:
   ```
   OPENAI_API_KEY=your_api_key_here
   ```
4. Run the application using 'python BackEnd/app.py' and access the local URL provided in the terminal. 

*Note: Local setup is optional. The app is primarily intended to be accessed via the hosted version.*

## Status
✅ Deployed  
⚠️ Experimental / Iterative improvements ongoing  

## Notes
This project focuses on practical GenAI workflow design, including:
- Context management  
- Prompt structuring  
- Local-first data architecture
