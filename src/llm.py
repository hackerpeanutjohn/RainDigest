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

    @abc.abstractmethod
    def classify_bookmark(self, title: str, note: str, collections: dict) -> Optional[int]:
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

    def analyze_visual_cues(self, transcript_with_timestamps: str) -> list:
        """
        Analyze transcript to find visual cue timestamps.
        Returns list of dicts: [{'timestamp': float, 'reason': str}]
        """
        system_prompt = """
你是一位專業的影片剪輯師與知識管理專家。
我會提供一份影片的逐字稿（包含時間戳記）。
你的任務是找出「畫面上最可能出現高價值資訊（如圖表、數據、關鍵字卡、條列重點）」的時間點。

請忽略：
1. 講者的純大頭畫面 (Talking head)。
2. 無意義的過場或玩笑。

請依照以下 JSON 格式回傳 3-5 個最重要的時間點：
[
  {
    "timestamp": 45.5,
    "reason": "講者提到'這張趨勢圖'，預期有數據圖表"
  },
  {
    "timestamp": 120.0,
    "reason": "講者開始列點'Step 1'，預期有文字卡"
  }
]
"""
        prompt = f"{system_prompt}\n\n逐字稿內容：\n{transcript_with_timestamps}"
        
        try:
            # Force JSON response if possible, or just parse text
            # Gemini 1.5/2.0 supports response_mime_type="application/json" usually
            # But let's rely on prompt first for compatibility
            response = self.model.generate_content(prompt)
            text = response.text
            
            # Clean markdown code blocks
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
                
            import json
            return json.loads(text.strip())
        except Exception as e:
            logger.error(f"Visual Cue Analysis failed: {e}")
            return []

    def analyze_visual_cues_from_audio(self, audio_path: Path) -> list:
        """
        Analyze AUDIO to find visual cue timestamps (fallback when no transcript).
        """
        system_prompt = """
你是一位專業的影片剪輯師。
請根據這段語音內容，判斷講者在什麼時間點「最可能」正在展示重要的視覺資訊（如圖表、清單、示範操作）。
請尋找語音線索，例如：「如圖所示」、「大家看這張表」、「第一點、第二點」等。

請依照以下 JSON 格式回傳 3-5 個最重要的時間點：
[
  {
    "timestamp": 45.5,
    "reason": "講者提到'這張圖'，預期有數據圖表"
  }
]
"""
        try:
            # Re-use the existing file upload logic if possible, or just upload here
            # Since process_audio uploads it, we might want to cache? 
            # For simplicity, we upload again or check if we can reuse (Gemini API is stateless unless we manage file lifecycle)
            # We will just upload/process normally.
            
            import time
            logger.info(f"Uploading audio for Visual Analysis: {audio_path}")
            audio_file = genai.upload_file(path=audio_path)
            
            # Wait for processing
            while audio_file.state.name == "PROCESSING":
                time.sleep(1)
                audio_file = genai.get_file(audio_file.name)
                
            if audio_file.state.name == "FAILED":
                logger.error("Audio processing failed.")
                return []
                
            response = self.model.generate_content([system_prompt, audio_file])
            text = response.text
            
            # Cleanup
            # genai.delete_file(audio_file.name) # Optional, or let it expire
            
            # Parse JSON
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
                
            import json
            return json.loads(text.strip())
            
        except Exception as e:
            logger.error(f"Audio Visual Analysis failed: {e}")
            return []

    def analyze_visual_cues_from_video(self, video_path: Path) -> list:
        """
        Analyze VIDEO (Visual + Audio) to find exact timestamps of key slides/charts.
        This is much more accurate than Audio-only analysis.
        """
        system_prompt = """
你是一位專業的知識影片剪輯師。你的任務是從影片中找出「含金量高」的視覺畫面。
請分析影片，找出畫面顯示「關鍵資訊」的時間點，例如：
1. **條列式清單** (Bulleted Lists)
2. **圖表/數據圖** (Charts/Graphs)
3. **文字總結卡片** (Summary Cards)
4. **具體操作步驟畫面** (Step-by-step UI/Process)

**排除原則**：
- 如果畫面只是「講者大頭照」(Talking Head)，不要截圖。
- 如果畫面只是「與內容無關的裝飾性動畫或梗圖」，不要截圖。
- 如果整部影片都沒有上述的高價值畫面，請回傳空陣列 `[]`。

請回傳 JSON 格式：
[
  {
    "timestamp": 12.5,
    "reason": "出現'核心法則'的三點清單"
  }
]
"""
        try:
            import time
            logger.info(f"Uploading Video to Gemini for Visual Analysis: {video_path.name}...")
            video_file = genai.upload_file(path=video_path)
            
            # Wait for processing (Video takes longer)
            while video_file.state.name == "PROCESSING":
                time.sleep(2)
                video_file = genai.get_file(video_file.name)
                
            if video_file.state.name == "FAILED":
                logger.error("Video processing failed.")
                return []
                
            logger.info("Video processed. Asking Gemini to find timestamps...")
            response = self.model.generate_content([system_prompt, video_file])
            text = response.text
            
            # Helper to parse JSON
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
                
            import json
            return json.loads(text.strip())
            
        except Exception as e:
            logger.error(f"Video Visual Analysis failed: {e}")
            return []

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

    def generate_concise_title(self, summary: str, original_title: str) -> str:
        """
        Generate a concise, descriptive title based on summary and metadata.
        """
        prompt = f"""
        Generate a concise (under 80 chars), descriptive filename-friendly title for this content.
        Do NOT use colons, slashes, or special characters.
        Use spaces or hyphens.
        
        Original Title: {original_title}
        Summary: {summary[:1000]}
        
        Title:
        """
        
        try:
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            logger.error(f"Title Gen Error: {e}")
            return original_title

    def classify_bookmark(self, title: str, note: str, collections: dict) -> Optional[int]:
        """
        Analyze the bookmark and suggest the best collection ID.
        Returns None if no suitable collection found or uncertain.
        """
        # Format collections for prompt
        cols_text = "\n".join([f"{cid}: {cname}" for cid, cname in collections.items()])
        
        prompt = f"""
        You are a highly organized personal librarian. 
        Analyze the following bookmark and categorize it into ONE of the provided collections.
        
        Bookmark Details:
        - Title: {title}
        - Note/Excerpt: {note[:500]}
        
        Available Collections (ID: Name):
        {cols_text}
        
        Instructions:
        1. Select the SINGLE BEST collection ID that fits this content.
        2. If the content fits multiple, choose the most specific one.
        3. If it doesn't fit ANY clearly, return "0".
        4. Return ONLY the ID number (integer).
        """
        
        try:
            response = self.model.generate_content(prompt)
            text = response.text.strip()
            # Cleanup possible markdown or extra chars
            text = "".join([c for c in text if c.isdigit()])
            if not text: return None
            
            cid = int(text)
            if cid == 0: return None
            return cid
            
        except Exception as e:
            logger.error(f"Classification Error: {e}")
            return None


def get_provider(name: str = "gemini") -> LLMProvider:
    return GeminiProvider()
