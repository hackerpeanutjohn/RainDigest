import abc
import os
from pathlib import Path
from typing import Optional
import google.generativeai as genai
from loguru import logger
from .config import settings, DEFAULT_SYSTEM_PROMPT

class LLMProvider(abc.ABC):
    @abc.abstractmethod
    def summarize_text(self, text: str) -> str:
        pass

    @abc.abstractmethod
    def process_audio(self, audio_path: Path) -> str:
        """
        Transcribe and/or Summarize directly from audio.
        Returns the summary.
        """
        pass

class GeminiProvider(LLMProvider):
    def __init__(self):
        if not settings.GEMINI_API_KEY:
            logger.warning("Gemini API Key not found.")
        else:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            # Try specific version 
            self.model_name = 'gemini-2.0-flash'
            self.model = genai.GenerativeModel(self.model_name) 

    def summarize_text(self, text: str) -> str:
        prompt = f"{DEFAULT_SYSTEM_PROMPT}\n\n逐字稿內容：\n{text}"
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Gemini Error on {self.model_name}: {e}")
            self._log_available_models()
            raise e

    def _log_available_models(self):
        try:
            logger.info("Listing available models...")
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    logger.info(f" - {m.name}")
        except Exception as e:
            logger.error(f"Failed to list models: {e}")

    def process_audio(self, audio_path: Path) -> str:
        import time
        logger.info(f"Uploading file to Gemini: {audio_path}")
        try:
            # Upload file
            audio_file = genai.upload_file(path=audio_path)
            
            # Wait for processing
            logger.info("Waiting for file processing...")
            while audio_file.state.name == "PROCESSING":
                time.sleep(2)
                audio_file = genai.get_file(audio_file.name)
                
            if audio_file.state.name == "FAILED":
                raise ValueError("Gemini file processing failed.")
            
            logger.info("File ready. Generating summary...")

            # Create prompt
            prompt = f"{DEFAULT_SYSTEM_PROMPT}\n\n(請根據提供的音訊檔進行整理)"
            
            # Generate
            response = self.model.generate_content([prompt, audio_file])
            return response.text
        except Exception as e:
            logger.error(f"Gemini processing error: {e}")
            raise e

def get_provider(name: str = "gemini") -> LLMProvider:
    return GeminiProvider()
