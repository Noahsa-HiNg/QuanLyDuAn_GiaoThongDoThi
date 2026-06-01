"""
services/audit.py — Decorator ghi nhận nhật ký hệ thống (Audit Log)
Được sử dụng cho các router cần lưu vết hoạt động bảo mật/quản trị.
"""

import functools
import inspect
import json
from sqlalchemy.orm import Session
from fastapi import Request
from models.audit_log import AuditLog


def audit_action(action: str, target_table: str = None):
    """
    Decorator để ghi lại hành động của người dùng vào bảng `audit_log`.
    Hỗ trợ cả hàm đồng bộ (sync) và bất đồng bộ (async).
    
    Yêu cầu:
      - Hàm được decorate phải có tham số `db: Session`
      - (Tùy chọn) Có `request: Request` để lấy địa chỉ IP
      - (Tùy chọn) Có `current_user: User` để biết ai thực hiện
    """
    def decorator(func):
        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                db = kwargs.get("db")
                request = kwargs.get("request")
                current_user = kwargs.get("current_user")
                
                # Tìm db trong args nếu không có trong kwargs
                if not db:
                    for arg in args:
                        if isinstance(arg, Session):
                            db = arg
                            break
                # Tìm request trong args
                if not request:
                    for arg in args:
                        if isinstance(arg, Request):
                            request = arg
                            break

                result = await func(*args, **kwargs)

                try:
                        user_id = getattr(current_user, "id", None)
                        if not user_id and result:
                            user_obj = getattr(result, "user", None)
                            if user_obj:
                                user_id = getattr(user_obj, "id", None)
                        
                        ip_address = request.client.host if request and request.client else None
                        target_id = getattr(result, "id", None)
                        
                        detail = {}
                        if "payload" in kwargs:
                            try:
                                if hasattr(kwargs["payload"], "model_dump_json"):
                                    payload_dict = json.loads(kwargs["payload"].model_dump_json())
                                elif hasattr(kwargs["payload"], "model_dump"):
                                    payload_dict = kwargs["payload"].model_dump(mode="json")
                                elif hasattr(kwargs["payload"], "dict"):
                                    payload_dict = json.loads(json.dumps(kwargs["payload"].dict(), default=str))
                                else:
                                    payload_dict = str(kwargs["payload"])
                                
                                if isinstance(payload_dict, dict):
                                    detail["payload"] = {
                                        k: v for k, v in payload_dict.items()
                                        if "password" not in k.lower()
                                    }
                                else:
                                    detail["payload"] = payload_dict
                            except Exception as pe:
                                print(f"[Audit Log Decorator Payload Parse Error] {pe}")
                                detail["payload"] = str(kwargs["payload"])

                        log_record = AuditLog(
                            user_id=user_id,
                            action=action,
                            target_table=target_table,
                            target_id=target_id,
                            ip_address=ip_address,
                            detail=detail if detail else None
                        )
                        db.add(log_record)
                        db.commit()
                except Exception as e:
                    print(f"[Audit Log Decorator Error] {e}")
                    if db:
                        try:
                            db.rollback()
                        except Exception:
                            pass

                return result
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                db = kwargs.get("db")
                request = kwargs.get("request")
                current_user = kwargs.get("current_user")
                
                if not db:
                    for arg in args:
                        if isinstance(arg, Session):
                            db = arg
                            break
                if not request:
                    for arg in args:
                        if isinstance(arg, Request):
                            request = arg
                            break

                result = func(*args, **kwargs)

                try:
                    if db:
                        user_id = getattr(current_user, "id", None)
                        if not user_id and result:
                            user_obj = getattr(result, "user", None)
                            if user_obj:
                                user_id = getattr(user_obj, "id", None)
                                
                        ip_address = request.client.host if request and request.client else None
                        target_id = getattr(result, "id", None)
                        
                        detail = {}
                        if "payload" in kwargs:
                            try:
                                if hasattr(kwargs["payload"], "model_dump_json"):
                                    payload_dict = json.loads(kwargs["payload"].model_dump_json())
                                elif hasattr(kwargs["payload"], "model_dump"):
                                    payload_dict = kwargs["payload"].model_dump(mode="json")
                                elif hasattr(kwargs["payload"], "dict"):
                                    payload_dict = json.loads(json.dumps(kwargs["payload"].dict(), default=str))
                                else:
                                    payload_dict = str(kwargs["payload"])
                                
                                if isinstance(payload_dict, dict):
                                    detail["payload"] = {
                                        k: v for k, v in payload_dict.items()
                                        if "password" not in k.lower()
                                    }
                                else:
                                    detail["payload"] = payload_dict
                            except Exception as pe:
                                print(f"[Audit Log Decorator Payload Parse Error] {pe}")
                                detail["payload"] = str(kwargs["payload"])

                        log_record = AuditLog(
                            user_id=user_id,
                            action=action,
                            target_table=target_table,
                            target_id=target_id,
                            ip_address=ip_address,
                            detail=detail if detail else None
                        )
                        db.add(log_record)
                        db.commit()
                except Exception as e:
                    print(f"[Audit Log Decorator Error] {e}")
                    if db:
                        try:
                            db.rollback()
                        except Exception:
                            pass

                return result
            return sync_wrapper
    return decorator
