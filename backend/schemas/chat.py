from pydantic import BaseModel
from typing import List

class ChatMessage(BaseModel):
    role: str      # Nhận giá trị: "user" (người dùng) hoặc "model" (trợ lý AI)
    content: str   # Nội dung văn bản của tin nhắn

class ChatRequest(BaseModel):
    message: str                 # Tin nhắn mới nhất của người dùng
    history: List[ChatMessage] = [] # Lịch sử hội thoại trước đó

class ChatResponse(BaseModel):
    response: str                # Phản hồi từ trợ lý AI
