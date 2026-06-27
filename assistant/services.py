import logging
import google.generativeai as genai
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger('app')

class GeminiClient:
    def __init__(self):
        self.api_key = getattr(settings, 'GEMINI_API_KEY', None)
        self.initialized = False
        
        # Check if API Key is configured
        if not self.api_key or self.api_key == "PLACEHOLDER_GEMINI_API_KEY" or self.api_key == "YOUR_GEMINI_API_KEY_HERE":
            logger.warning("Gemini API Key is not configured. Running Gemini Client in MOCK mode.")
            return

        try:
            # Configure Google Generative AI with the API Key
            genai.configure(api_key=self.api_key)
            self.model_name = "gemini-1.5-flash"
            self.system_instruction = (
                "You are the brain of a friendly, advanced AI Humanoid Robot. "
                "Keep your answers brief, natural, conversational, and direct (maximum 1-2 sentences). "
                "Do not use markdown formatting like asterisks or bold text, as your response will be read aloud by a Text-to-Speech system."
            )
            self.initialized = True
            logger.info("Gemini API Client successfully initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini API Client: {str(e)}")

    def generate_response(self, prompt: str, session_id: str = None) -> str:
        """
        Queries the Gemini model with a prompt.
        If a session_id is provided, it retrieves conversation history from the cache and appends to it.
        """
        if not self.initialized:
            # Fallback to mock replies during development or when API key is missing
            return self._generate_mock_response(prompt)
            
        try:
            history_key = f"chat_history_{session_id}" if session_id else None
            history = cache.get(history_key, []) if history_key else []
            
            # Instantiate the generative model with the system instruction
            model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=self.system_instruction
            )
            
            # Format the cached history to matches Gemini API expectation
            api_history = []
            for item in history:
                api_history.append({
                    'role': 'user' if item['role'] == 'user' else 'model',
                    'parts': [item['content']]
                })
            
            # Start chat session with history
            chat = model.start_chat(history=api_history)
            response = chat.send_message(prompt)
            reply = response.text.strip()
            
            # Update history cache
            if history_key:
                history.append({'role': 'user', 'content': prompt})
                history.append({'role': 'model', 'content': reply})
                # Limit history to last 10 turns (20 entries) to prevent token size blowout
                if len(history) > 20:
                    history = history[-20:]
                cache.set(history_key, history, timeout=1800) # Keep for 30 minutes
                
            return reply
            
        except Exception as e:
            logger.error(f"Error calling Gemini API: {str(e)}", exc_info=True)
            return self._generate_fallback_response(prompt, str(e))

    def _generate_mock_response(self, prompt: str) -> str:
        """Mock response handler if API key is not configured."""
        prompt_lower = prompt.lower()
        if "hello" in prompt_lower or "hi " in prompt_lower or prompt_lower == "hi":
            return "Hello! I am online and listening. However, my Gemini API key is not configured yet. Please configure it to chat with me fully."
        if "your name" in prompt_lower or "who are you" in prompt_lower:
            return "I am a humanoid robot helper. I am currently running in mock mode because my Gemini API key is missing."
        if "look" in prompt_lower or "turn" in prompt_lower or "head" in prompt_lower or "eyes" in prompt_lower:
            return f"Understood, I am parsing your movement command. Moving now."
        return "Please configure the GEMINI_API_KEY in the env file to enable my full AI brain."

    def _generate_fallback_response(self, prompt: str, error_msg: str) -> str:
        """Graceful response fallback if API requests fail at runtime."""
        logger.warning(f"Using fallback response due to error: {error_msg}")
        prompt_lower = prompt.lower()
        if "hello" in prompt_lower or "hi" in prompt_lower:
            return "Hello! I am currently experiencing some network trouble, but I can hear you."
        return "I encountered an error trying to process that. Please check my server logs or internet connection."
