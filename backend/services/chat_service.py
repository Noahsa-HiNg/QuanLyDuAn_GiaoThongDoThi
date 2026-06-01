import httpx
import logging
from sqlalchemy.orm import Session
from config import settings

logger = logging.getLogger(__name__)

def chat_with_gemini(db: Session, message: str, history: list[dict]) -> str:
    """
    Gửi tin nhắn của người dùng và lịch sử trò chuyện đến Google Gemini API (gemini-2.5-flash)
    và nhận phản hồi dạng văn bản. Chưa áp dụng RAG/truy vấn động dữ liệu thực tế theo yêu cầu.
    """
    # 1. Lấy API Key từ cấu hình
    api_key = settings.gemini_api_key
    if not api_key:
        logger.error("Missing GEMINI_API_KEY in configuration settings.")
        return "⚠️ Lỗi: Chưa cấu hình GEMINI_API_KEY trên máy chủ."
        
    # 2. Xây dựng System Instruction (Chỉ dẫn hệ thống cố định)
    system_instruction = (
        "Bạn là Trợ lý AI Giao thông thông minh của thành phố Đà Nẵng. "
        "Nhiệm vụ của bạn là hỗ trợ và cung cấp thông tin giao thông một cách chính xác, tự nhiên, thân thiện và hữu ích bằng tiếng Việt.\n\n"
        "HƯỚNG DẪN TRẢ LỜI:\n"
        "1. Trả lời ngắn gọn, cô đọng, dễ hiểu (không dông dài hay lặp lại các số liệu không cần thiết).\n"
        "2. Nếu người dùng hỏi đường đi chi tiết hoặc tìm lộ trình tối ưu, hãy hướng dẫn họ sử dụng tính năng 'Tìm đường' (Route Finder) có sẵn trên thanh menu/giao diện bản đồ của hệ thống để được AI vạch đường né kẹt xe tối ưu nhất.\n"
        "3. Giữ giọng điệu lịch sự, chuyên nghiệp nhưng vẫn gần gũi với người dân."
    )
    
    # 3. Định dạng lại danh sách contents với lịch sử + tin nhắn hiện tại
    contents = []
    for msg in history:
        role = msg.get("role")
        content = msg.get("content")
        
        # Chỉ chấp nhận role hợp lệ là "user" hoặc "model"
        if role in ["user", "model"]:
            contents.append({
                "role": role,
                "parts": [{"text": content}]
            })
            
    # Thêm câu hỏi hiện tại của user vào cuối
    contents.append({
        "role": "user",
        "parts": [{"text": message}]
    })
    
    # 4. Cấu hình endpoint API phù hợp cho từng model (v1 cho stable, v1beta cho preview)
    # và cơ chế fallback tự động chuyển đổi khi gặp bất kỳ lỗi kết nối nào
    models_config = [
        {"name": "gemini-3.5-flash", "version": "v1beta"},
        {"name": "gemini-2.5-flash", "version": "v1beta"},
        {"name": "gemini-2.0-flash", "version": "v1"},
        {"name": "gemini-1.5-flash", "version": "v1"}
    ]
    
    payload = {
        "contents": contents,
        "systemInstruction": {
            "parts": [
                {"text": system_instruction}
            ]
        }
    }
    
    last_error_code = None
    last_error_text = ""
    
    for model in models_config:
        model_name = model["name"]
        api_ver = model["version"]
        url = f"https://generativelanguage.googleapis.com/{api_ver}/models/{model_name}:generateContent?key={api_key}"
        
        try:
            logger.info(f"Attempting to call Gemini model: {model_name} via {api_ver}")
            response = httpx.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=15.0
            )
            
            # Nếu có lỗi (status code != 200), ghi nhận và tiếp tục thử model dự phòng tiếp theo
            if response.status_code != 200:
                logger.warning(f"Model {model_name} returned status {response.status_code}: {response.text}. Retrying fallback...")
                last_error_code = response.status_code
                last_error_text = response.text
                continue
                
            resp_json = response.json()
            
            # Trích xuất nội dung trả về
            candidates = resp_json.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "Không có nội dung phản hồi từ trợ lý.")
            
            logger.error(f"Gemini API returned unexpected response format for {model_name}: {resp_json}")
            last_error_code = 500
            last_error_text = "Unexpected response format"
            continue
            
        except httpx.HTTPStatusError as e:
            logger.warning(f"Model {model_name} failed with HTTP status {e.response.status_code}: {e.response.text}. Retrying fallback...")
            last_error_code = e.response.status_code
            last_error_text = e.response.text
            continue
        except Exception as e:
            logger.error(f"Error calling model {model_name}: {e}")
            last_error_code = 500
            last_error_text = str(e)
            continue
            
    # Nếu tất cả các model đều lỗi hoặc quá tải
    if last_error_code:
        return f"⚠️ Lỗi kết nối Gemini API (Mã lỗi: {last_error_code}). Máy chủ trợ lý hiện đang bận hoặc quá tải, vui lòng thử lại sau ít phút."
    return "⚠️ Đã xảy ra lỗi khi liên lạc với máy chủ Trợ lý AI."
