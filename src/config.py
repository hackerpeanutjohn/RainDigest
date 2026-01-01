import os
from typing import Optional
from pathlib import Path
from pydantic import Field
from dotenv import load_dotenv

# Load .env file
load_dotenv()

class Settings:
    # Raindrop
    RAINDROP_TOKEN: str = os.getenv("RAINDROP_TEST_TOKEN", os.getenv("RAINDROP_TOKEN", ""))
    RAINDROP_COLLECTION_ID: int = int(os.getenv("RAINDROP_COLLECTION_ID", "0"))
    APP_USER_AGENT: str = os.getenv("APP_USER_AGENT", "RaindropVideoSummarizer/1.0")
    
    # Readwise
    READWISE_TOKEN: Optional[str] = os.getenv("READWISE_TOKEN")
    
    # LLM
    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY")
    
    # Paths
    OUTPUT_DIR: Path = Path(os.getenv("OUTPUT_DIR", "./output"))
    DATA_DIR: Path = Path(os.getenv("DATA_DIR", "./data"))
    
    # System
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Cloudflare R2
    R2_ACCOUNT_ID: Optional[str] = os.getenv("R2_ACCOUNT_ID")
    R2_ACCESS_KEY_ID: Optional[str] = os.getenv("R2_ACCESS_KEY_ID")
    R2_SECRET_ACCESS_KEY: Optional[str] = os.getenv("R2_SECRET_ACCESS_KEY")
    R2_BUCKET_NAME: Optional[str] = os.getenv("R2_BUCKET_NAME")
    R2_PUBLIC_DOMAIN: Optional[str] = os.getenv("R2_PUBLIC_DOMAIN")
    
    # Debug Control
    DRY_RUN: bool = os.getenv("DRY_RUN", "false").lower() == "true"
    MAX_ITEMS: int = int(os.getenv("MAX_ITEMS", "50"))
    
    # Defaults
    DEFAULT_LLM_PROVIDER: str = "gemini" 

    def validate(self):
        if not self.RAINDROP_TOKEN:
            raise ValueError(
                "RAINDROP_TOKEN is missing. Please check your .env file. "
                "See README.md -> 'Review Required' or 'Setup' section for instructions."
            )
        
        self.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)

settings = Settings()

# Prompts
DEFAULT_SYSTEM_PROMPT = """
你是一位具備批判性思維的學習助理。請根據以下逐字稿，為我生成一份適合閱讀的「前導摘要」。

請依照以下規則輸出（不要包含任何標籤或外部連結建議）：

### 1. 核心精華 (The Gist)
* 用 3 句話告訴我：這段影片試圖解決什麼問題？講者的核心解法是什麼？

### 2. 關鍵知識點 (Key Takeaways)
* 如果有具體步驟，請整理成 Step 1, Step 2...
* 如果是觀念分享，請列出 3 個最重要的 Insight（盡量保留講者的獨特觀點或用語）。

### 3. 批判性視角 (Critical Lens)
* **適用邊界**：講者的方法在什麼情況下可能**無效**或**危險**？
* **未解之謎**：講者有沒有忽略了什麼重要的變數？（例如：只談營收沒談利潤、只談成長沒談心理健康）
* (若內容無明顯漏洞，此區塊可省略，不要硬寫)

---
(以下為原始逐字稿，請保留給用戶查閱)
"""
