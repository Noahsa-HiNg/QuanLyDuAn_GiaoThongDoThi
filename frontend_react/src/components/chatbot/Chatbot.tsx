// frontend_react/src/components/chatbot/Chatbot.tsx

import React, { useState, useEffect, useRef } from 'react';
import { MessageSquare, X, Send, Bot, User, Move, RefreshCw } from 'lucide-react';
import { trafficApi } from '../../api/traffic.api';
import type { ChatMessage as ApiChatMessage } from '../../api/traffic.api';

interface Message {
  id: string;
  sender: 'user' | 'bot';
  text: string;
  timestamp: Date;
}

const Chatbot: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [inputText, setInputText] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [isTyping, setIsTyping] = useState(false);

  // Dragging state
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const dragStart = useRef({ x: 0, y: 0 });
  const elementStart = useRef({ x: 0, y: 0 });
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Global toggle listener
  useEffect(() => {
    const handleToggle = () => setIsOpen((prev) => !prev);
    window.addEventListener('chat-widget-toggle', handleToggle);
    return () => window.removeEventListener('chat-widget-toggle', handleToggle);
  }, []);

  // Set initial position on mount (bottom-right, left of zoom controls)
  useEffect(() => {
    const initX = window.innerWidth - 136;
    const initY = window.innerHeight - 76;
    setPosition({ x: initX, y: initY });

    // Add welcome message
    setMessages([
      {
        id: 'welcome',
        sender: 'bot',
        text: '👋 Xin chào! Tôi là **Trợ lý ảo Giao thông Đà Nẵng**.\n\nTôi có thể cung cấp thông tin thời gian thực về kẹt xe, thời tiết Đà Nẵng, danh sách sự cố, tình hình CSGT đang trực ban hoặc giải đáp chi tiết về công nghệ AI sử dụng trong dự án.\n\nHãy chọn một chủ đề gợi ý nhanh bên dưới hoặc nhập câu hỏi của bạn nhé!',
        timestamp: new Date(),
      },
    ]);
  }, []);

  // Sync position on window resize
  useEffect(() => {
    const handleResize = () => {
      setPosition((prev) => {
        const nextX = Math.max(10, Math.min(prev.x, window.innerWidth - 136));
        const nextY = Math.max(10, Math.min(prev.y, window.innerHeight - 76));
        return { x: nextX, y: nextY };
      });
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);


  // Scroll to bottom when messages update
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isTyping]);

  // Handle Drag Start
  const handleMouseDown = (e: React.MouseEvent<HTMLButtonElement>) => {
    if (e.button !== 0) return; // Left click only
    setIsDragging(false);
    dragStart.current = { x: e.clientX, y: e.clientY };
    elementStart.current = { x: position.x, y: position.y };

    const handleMouseMove = (moveEvent: MouseEvent) => {
      const dx = moveEvent.clientX - dragStart.current.x;
      const dy = moveEvent.clientY - dragStart.current.y;

      if (Math.abs(dx) > 6 || Math.abs(dy) > 6) {
        setIsDragging(true);
      }

      let nextX = elementStart.current.x + dx;
      let nextY = elementStart.current.y + dy;

      // Clamp within viewport bounds
      nextX = Math.max(10, Math.min(nextX, window.innerWidth - 70));
      nextY = Math.max(10, Math.min(nextY, window.innerHeight - 70));

      setPosition({ x: nextX, y: nextY });
    };

    const handleMouseUp = () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
  };

  const handleButtonClick = () => {
    if (!isDragging) {
      setIsOpen(!isOpen);
    }
  };

  // Helper formatting Markdown-like bold, lists, and highlighting key terms in chatbot messages
  const formatMessageText = (text: string, sender: 'user' | 'bot') => {
    return text.split('\n').map((line, idx) => {
      let formatted = line;

      // 1. Nếu là chatbot trả lời, tự động highlight các từ khoá giao thông quan trọng
      if (sender === 'bot') {
        const greenKeywords = ['thông thoáng', 'ổn định', 'bình thường', 'an toàn'];
        const redKeywords = ['ùn tắc', 'kẹt xe', 'ùn ứ', 'nghẽn', 'tắc nghẽn'];
        const yellowKeywords = ['sự cố', 'tai nạn', 'va chạm', 'ngập lụt', 'ngập nước'];
        const blueKeywords = ['CSGT', 'cảnh sát giao thông', 'lực lượng chức năng', 'điều tiết'];

        greenKeywords.forEach(kw => {
          const regex = new RegExp(`(${kw})`, 'gi');
          formatted = formatted.replace(regex, '<span class="text-emerald-400 font-semibold bg-emerald-500/10 px-1.5 py-0.5 rounded">$1</span>');
        });
        redKeywords.forEach(kw => {
          const regex = new RegExp(`(${kw})`, 'gi');
          formatted = formatted.replace(regex, '<span class="text-rose-400 font-semibold bg-rose-500/10 px-1.5 py-0.5 rounded">$1</span>');
        });
        yellowKeywords.forEach(kw => {
          const regex = new RegExp(`(${kw})`, 'gi');
          formatted = formatted.replace(regex, '<span class="text-amber-400 font-semibold bg-amber-500/10 px-1.5 py-0.5 rounded">$1</span>');
        });
        blueKeywords.forEach(kw => {
          const regex = new RegExp(`(${kw})`, 'gi');
          formatted = formatted.replace(regex, '<span class="text-sky-400 font-semibold bg-sky-500/10 px-1.5 py-0.5 rounded">$1</span>');
        });
      }

      // 2. Bold **text** -> Highlight màu hồng
      formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong class="text-pink-400 font-bold bg-pink-500/10 px-1.5 py-0.5 rounded">$1</strong>');
      // 3. Italic *text* -> Highlight màu xanh
      formatted = formatted.replace(/\*(.*?)\*/g, '<em class="text-blue-300 not-italic bg-blue-500/10 px-1.5 py-0.5 rounded">$1</em>');
      
      if (line.startsWith('- ') || line.startsWith('+ ') || line.startsWith('* ')) {
        const content = formatted.replace(/^[-+*]\s/, '');
        return (
          <li key={idx} className="ml-4 list-disc my-1" dangerouslySetInnerHTML={{ __html: content }} />
        );
      }
      if (line.match(/^\d+\.\s/)) {
        const content = formatted.replace(/^\d+\.\s/, '');
        return (
          <li key={idx} className="ml-4 list-decimal my-1" dangerouslySetInnerHTML={{ __html: content }} />
        );
      }
      return (
        <p key={idx} className="min-h-[1.2em] my-1" dangerouslySetInnerHTML={{ __html: formatted }} />
      );
    });
  };

  const sendMessage = async (textToSend: string) => {
    if (!textToSend.trim()) return;

    const userMsg: Message = {
      id: Math.random().toString(36).substring(7),
      sender: 'user',
      text: textToSend,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputText('');
    setIsTyping(true);

    try {
      const historyPayload: ApiChatMessage[] = messages
        .filter((msg) => msg.id !== 'welcome')
        .map((msg) => ({
          role: msg.sender === 'user' ? 'user' : 'model',
          content: msg.text,
        }));
      const response = await trafficApi.chat(textToSend, historyPayload);
      const botReply = response.response || 'Tôi chưa tìm thấy phản hồi phù hợp.';
      
      setMessages((prev) => [
        ...prev,
        {
          id: Math.random().toString(36).substring(7),
          sender: 'bot',
          text: botReply,
          timestamp: new Date(),
        },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          id: Math.random().toString(36).substring(7),
          sender: 'bot',
          text: '⚠️ Không thể kết nối với máy chủ Trợ lý ảo. Vui lòng kiểm tra lại backend.',
          timestamp: new Date(),
        },
      ]);
    } finally {
      setIsTyping(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      sendMessage(inputText);
    }
  };

  const quickChips = [
    { label: '🌡️ Thời tiết', text: 'Xem thời tiết' },
    { label: '🚦 Kẹt xe', text: 'Xem các điểm kẹt xe' },
    { label: '🚨 Sự cố', text: 'Có sự cố giao thông nào đang xảy ra không' },
    { label: '👮 CSGT trực ban', text: 'Chiến sĩ nào đang rảnh' },
    { label: '❓ Hướng dẫn sử dụng', text: 'Hướng dẫn sử dụng hệ thống' },
    { label: '🤖 Mô hình AI', text: 'Hệ thống dùng mô hình AI nào dự báo' },
  ];

  // Dynamic clamping for Chat Window position based on the floating button position
  let chatLeft = position.x - 330;
  let chatTop = position.y - 520;

  chatLeft = Math.max(16, Math.min(chatLeft, window.innerWidth - 400));
  chatTop = Math.max(16, Math.min(chatTop, window.innerHeight - 520));

  return (
    <>
      {/* Draggable Chatbot Bubble Button */}
      <button
        onMouseDown={handleMouseDown}
        onClick={handleButtonClick}
        style={{ left: position.x, top: position.y }}
        className={`fixed z-[999] w-14 h-14 rounded-full flex items-center justify-center shadow-2xl transition cursor-grab active:cursor-grabbing border ${
          isOpen
            ? 'bg-slate-900 border-pink-500/40 text-pink-400 shadow-pink-500/20'
            : 'bg-gradient-to-tr from-blue-600 to-pink-600 border-white/20 text-white shadow-blue-500/20 hover:scale-105'
        }`}
        title="Kéo thả để di chuyển. Nhấp chuột để trò chuyện với Trợ lý ảo."
      >
        {isOpen ? <X size={24} /> : <MessageSquare size={24} />}
        {!isOpen && (
          <span className="absolute -top-1 -right-1 flex h-4 w-4">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-pink-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-4 w-4 bg-pink-500 items-center justify-center text-[8px] font-bold text-white">AI</span>
          </span>
        )}
      </button>

      {/* Glassmorphism Chat Window */}
      {isOpen && (
        <div
          style={{ left: chatLeft, top: chatTop }}
          className="fixed z-[998] w-[370px] h-[500px] rounded-2xl bg-slate-950/85 backdrop-blur-xl border border-white/10 shadow-2xl flex flex-col overflow-hidden animate-fade-in"
        >
          {/* Header */}
          <div className="bg-gradient-to-r from-blue-600/40 to-pink-600/40 border-b border-white/10 p-4 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-full bg-pink-500/20 border border-pink-500/40 flex items-center justify-center text-pink-400">
                <Bot size={18} />
              </div>
              <div>
                <h4 className="text-xs font-bold text-white tracking-wide">Trợ lý ảo Đà Nẵng</h4>
                <div className="flex items-center gap-1 mt-0.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse"></span>
                  <span className="text-[9px] text-green-400 font-bold uppercase tracking-wider">Trực tuyến</span>
                </div>
              </div>
            </div>
            
            <div className="flex items-center gap-1 text-slate-400">
              <div className="p-1 rounded bg-white/5 border border-white/5 cursor-move" title="Nút chat bên cạnh có thể kéo thả tự do">
                <Move size={12} />
              </div>
              <button
                onClick={() => setIsOpen(false)}
                className="p-1 hover:bg-white/10 hover:text-white rounded transition cursor-pointer"
              >
                <X size={16} />
              </button>
            </div>
          </div>

          {/* Messages Area */}
          <div className="flex-grow p-4 overflow-y-auto space-y-3 custom-scrollbar">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex gap-2 max-w-[85%] ${
                  msg.sender === 'user' ? 'ml-auto flex-row-reverse' : ''
                }`}
              >
                <div
                  className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] shrink-0 ${
                    msg.sender === 'user'
                      ? 'bg-blue-600 text-white'
                      : 'bg-pink-600/20 border border-pink-500/40 text-pink-400'
                  }`}
                >
                  {msg.sender === 'user' ? <User size={12} /> : <Bot size={12} />}
                </div>

                <div
                  className={`p-3 rounded-2xl text-xs leading-relaxed space-y-1.5 shadow-sm border ${
                    msg.sender === 'user'
                      ? 'bg-blue-600/80 border-blue-500/20 text-white rounded-tr-none'
                      : 'bg-white/5 border-white/5 text-slate-200 rounded-tl-none'
                  }`}
                >
                  {formatMessageText(msg.text, msg.sender === 'user' ? 'user' : 'bot')}
                  <span className="block text-[8px] text-slate-400 text-right mt-1 font-mono">
                    {msg.timestamp.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>
              </div>
            ))}

            {isTyping && (
              <div className="flex gap-2 max-w-[80%]">
                <div className="w-6 h-6 rounded-full bg-pink-600/20 border border-pink-500/40 flex items-center justify-center text-pink-400 shrink-0">
                  <Bot size={12} />
                </div>
                <div className="p-3 rounded-2xl bg-white/5 border border-white/5 text-slate-300 rounded-tl-none flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-pink-400 animate-bounce" style={{ animationDelay: '0ms' }}></span>
                  <span className="w-1.5 h-1.5 rounded-full bg-pink-400 animate-bounce" style={{ animationDelay: '150ms' }}></span>
                  <span className="w-1.5 h-1.5 rounded-full bg-pink-400 animate-bounce" style={{ animationDelay: '300ms' }}></span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Quick chips (Suggetions) */}
          <div className="px-4 py-2 border-t border-white/5 bg-slate-950/20 flex gap-1.5 overflow-x-auto whitespace-nowrap scrollbar-none scroll-smooth shrink-0">
            {quickChips.map((chip, idx) => (
              <button
                key={idx}
                onClick={() => sendMessage(chip.text)}
                disabled={isTyping}
                className="bg-white/5 border border-white/10 text-[10px] px-3 py-1.5 rounded-full hover:bg-white/15 hover:border-pink-500/30 hover:text-pink-400 text-slate-300 font-medium transition cursor-pointer disabled:opacity-50 flex items-center justify-center shrink-0 h-[28px]"
              >
                {chip.label}
              </button>
            ))}
          </div>

          {/* Input field */}
          <div className="p-3 border-t border-white/10 bg-slate-950/40 flex items-center gap-2 shrink-0">
            <input
              type="text"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={handleKeyPress}
              disabled={isTyping}
              placeholder="Hỏi về thời tiết, kẹt xe, CSGT..."
              className="flex-grow bg-slate-900 border border-white/10 rounded-xl px-3.5 py-2 text-xs text-white focus:outline-none focus:border-pink-500/50 placeholder-slate-500 transition disabled:opacity-50"
            />
            <button
              onClick={() => sendMessage(inputText)}
              disabled={!inputText.trim() || isTyping}
              className="p-2 bg-gradient-to-tr from-blue-600 to-pink-600 hover:scale-105 text-white rounded-xl shadow-md transition cursor-pointer disabled:opacity-50 disabled:scale-100"
            >
              <Send size={14} />
            </button>
          </div>
        </div>
      )}
    </>
  );
};

export default Chatbot;
