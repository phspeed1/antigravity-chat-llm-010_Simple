import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '../AuthContext';
import { Link } from 'react-router-dom';

export default function Chat() {
    const { user, logout } = useAuth();
    const API_BASE_URL = window.location.hostname === 'localhost'
        ? 'http://localhost:8000'
        : `http://${window.location.hostname}:8000`;

    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const [sessions, setSessions] = useState([]);
    const [currentSessionId, setCurrentSessionId] = useState(null);
    const [editingSessionId, setEditingSessionId] = useState(null);
    const [editTitle, setEditTitle] = useState('');
    const [model, setModel] = useState('gpt-4o-mini');

    const inputRef = useRef(null);

    // Fetch sessions on mount
    useEffect(() => {
        fetchSessions();
    }, []);

    // Fetch messages when session changes
    useEffect(() => {
        if (currentSessionId) {
            fetchMessages(currentSessionId);
            // Focus input when session changes
            setTimeout(() => inputRef.current?.focus(), 100);
        } else {
            setMessages([]);
        }
    }, [currentSessionId]);

    const fetchSessions = async () => {
        try {
            const token = localStorage.getItem('token');
            const res = await fetch(`${API_BASE_URL}/sessions`, {
                headers: { 'Authorization': `Bearer ${token} ` }
            });
            const data = await res.json();
            setSessions(data);
            if (data.length > 0 && !currentSessionId) {
                setCurrentSessionId(data[0].id);
            }
        } catch (error) {
            console.error('Error fetching sessions:', error);
        }
    };

    const fetchMessages = async (sessionId) => {
        try {
            const token = localStorage.getItem('token');
            const res = await fetch(`${API_BASE_URL}/sessions/${sessionId}/messages`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const data = await res.json();
            setMessages(data);
        } catch (error) {
            console.error('Error fetching messages:', error);
        }
    };

    const handleCreateSession = async () => {
        try {
            const token = localStorage.getItem('token');
            const res = await fetch(`${API_BASE_URL}/sessions`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({ title: 'New Chat' })
            });
            const newSession = await res.json();
            setSessions(prev => [newSession, ...prev]);
            setCurrentSessionId(newSession.id);
        } catch (error) {
            console.error('Error creating session:', error);
        }
    };

    const startEditing = (session) => {
        setEditingSessionId(session.id);
        setEditTitle(session.title);
    };

    const saveTitle = async () => {
        if (!editTitle.trim()) {
            setEditingSessionId(null);
            return;
        }
        try {
            const token = localStorage.getItem('token');
            const res = await fetch(`${API_BASE_URL}/sessions/${editingSessionId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({ title: editTitle })
            });

            if (res.ok) {
                setSessions(prev => prev.map(s =>
                    s.id === editingSessionId ? { ...s, title: editTitle } : s
                ));
            }
        } catch (error) {
            console.error('Error renaming session:', error);
        } finally {
            setEditingSessionId(null);
        }
    };

    const deleteSession = async (sessionId) => {
        if (!window.confirm('Are you sure you want to delete this session?')) return;

        try {
            const token = localStorage.getItem('token');
            const res = await fetch(`${API_BASE_URL}/sessions/${sessionId}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (res.ok) {
                setSessions(prev => prev.filter(s => s.id !== sessionId));
                if (currentSessionId === sessionId) {
                    setCurrentSessionId(null);
                    setMessages([]);
                }
            }
        } catch (error) {
            console.error('Error deleting session:', error);
        }
    };



    const handleSend = async (e) => {
        e.preventDefault();
        if (!input.trim() || !currentSessionId) return;

        const userMessage = { role: 'user', content: input };
        setMessages(prev => [...prev, userMessage]);
        setInput('');
        setLoading(true);

        try {
            const token = localStorage.getItem('token');
            const res = await fetch(`${API_BASE_URL}/chat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({
                    message: userMessage.content,
                    session_id: currentSessionId,
                    model: model
                })
            });

            if (!res.ok) {
                const errData = await res.json();
                throw new Error(errData.detail || 'Failed to get response');
            }

            const data = await res.json();
            // Update the last user message with token count if backend sends it back (optional optimization)
            // But we'll just append the assistant message which definitely has it.
            // If we want to show user tokens immediately, we'd update the previous message.
            setMessages(prev => {
                const newMsgs = [...prev];
                // Update user message token count if provided (assuming it is the last one)
                if (data.user_tokens) {
                    newMsgs[newMsgs.length - 1].tokenCount = data.user_tokens;
                }
                return [...newMsgs, { role: 'assistant', content: data.response, tokenCount: data.ai_tokens }];
            });

        } catch (error) {
            console.error(error);
            setMessages(prev => [...prev, { role: 'error', content: `Error: ${error.message}` }]);
        } finally {
            setLoading(false);
            // Focus input after response
            setTimeout(() => inputRef.current?.focus(), 100);
        }
    };

    return (
        <div className="flex h-full bg-gray-100">
            {/* Sidebar */}
            <div className="w-64 bg-gray-900 text-white flex flex-col">
                <div className="p-4 border-b border-gray-700">
                    <button
                        onClick={handleCreateSession}
                        className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-medium py-2 px-4 rounded transition duration-200 flex items-center justify-center gap-2 cursor-pointer"
                    >
                        <span>+</span> New Chat
                    </button>
                </div>

                <div className="flex-1 overflow-y-auto p-2 space-y-1">
                    {sessions.map(session => (
                        <div key={session.id} className="group relative">
                            {editingSessionId === session.id ? (
                                <input
                                    type="text"
                                    value={editTitle}
                                    onChange={(e) => setEditTitle(e.target.value)}
                                    onBlur={saveTitle}
                                    onKeyDown={(e) => e.key === 'Enter' && saveTitle()}
                                    autoFocus
                                    className="w-full px-3 py-2 bg-gray-700 text-white rounded outline-none border border-indigo-500"
                                />
                            ) : (
                                <div className="flex items-center">
                                    <button
                                        onClick={() => setCurrentSessionId(session.id)}
                                        className={`flex-1 text-left px-3 py-2 rounded truncate transition pr-16 cursor-pointer ${currentSessionId === session.id
                                            ? 'bg-gray-700 text-white'
                                            : 'text-gray-400 hover:bg-gray-800 hover:text-white'
                                            }`}
                                    >
                                        {session.title || 'Untitled Chat'}
                                    </button>
                                    <div className="absolute right-2 flex gap-1 items-center h-full">
                                        <button
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                startEditing(session);
                                            }}
                                            className="text-gray-500 hover:text-white p-1.5 rounded hover:bg-gray-600 transition-colors cursor-pointer"
                                            title="Rename"
                                        >
                                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4">
                                                <path strokeLinecap="round" strokeLinejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0 1 15.75 21H5.25A2.25 2.25 0 0 1 3 18.75V8.25A2.25 2.25 0 0 1 5.25 6H10" />
                                            </svg>
                                        </button>
                                        <button
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                deleteSession(session.id);
                                            }}
                                            className="text-gray-500 hover:text-red-400 p-1.5 rounded hover:bg-gray-600 transition-colors cursor-pointer"
                                            title="Delete"
                                        >
                                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4">
                                                <path strokeLinecap="round" strokeLinejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0" />
                                            </svg>
                                        </button>
                                    </div>
                                </div>
                            )}
                        </div>
                    ))}
                </div>

                <div className="p-4 border-t border-gray-700">
                    <div className="flex items-center gap-2">
                        {user?.avatar && (
                            <img src={user.avatar} alt="User" className="w-8 h-8 rounded-full" />
                        )}
                        <span className="truncate text-sm font-medium">{user?.name}</span>
                    </div>
                </div>
            </div>



            {/* Main Chat Area */}
            <div className="flex-1 flex flex-col min-w-0">
                {/* Header */}
                <div className="bg-white shadow p-4 flex justify-between items-center z-10">
                    <h1 className="text-xl font-bold text-gray-800">
                        {sessions.find(s => s.id === currentSessionId)?.title || 'Chat'}
                    </h1>
                </div>

                {/* Messages */}
                <div className="flex-1 overflow-y-auto p-4 space-y-4">
                    {messages.length === 0 ? (
                        <div className="flex flex-col items-center justify-center h-full text-gray-400 space-y-4">
                            <span className="text-6xl">💬</span>
                            <p>Start a new conversation!</p>
                        </div>
                    ) : (
                        messages.map((msg, index) => (
                            <div key={index} className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
                                <div className={`max-w-2xl p-4 rounded-xl shadow-sm ${msg.role === 'user'
                                    ? 'bg-indigo-600 text-white rounded-br-none'
                                    : 'bg-white text-gray-800 rounded-bl-none border border-gray-100'
                                    }`}>
                                    <div className="whitespace-pre-wrap">{msg.content}</div>
                                </div>
                                {msg.tokenCount !== undefined && msg.tokenCount !== null && (
                                    <span className="text-xs text-gray-400 mt-1 px-1">
                                        {msg.tokenCount} tokens
                                    </span>
                                )}
                            </div>
                        ))
                    )}
                    {loading && (
                        <div className="flex justify-start">
                            <div className="bg-white text-gray-500 p-4 rounded-xl shadow-sm rounded-bl-none border border-gray-100">
                                <div className="flex space-x-2">
                                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.4s' }}></div>
                                </div>
                            </div>
                        </div>
                    )}
                </div>

                {/* Input Area */}
                <div className="bg-white p-4 border-t">
                    <form onSubmit={handleSend} className="flex space-x-4 max-w-4xl mx-auto">
                        <input
                            ref={inputRef}
                            type="text"
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            placeholder="Type a message..."
                            disabled={loading || !currentSessionId}
                            autoFocus
                            className="flex-1 border border-gray-300 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50 disabled:bg-gray-50"
                        />
                        <button
                            type="submit"
                            disabled={loading || !currentSessionId}
                            className={`px-8 py-3 bg-indigo-600 text-white rounded-lg font-bold hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 transition-colors ${loading || !currentSessionId ? 'opacity-50 cursor-not-allowed' : ''}`}
                        >
                            Send
                        </button>
                        <div className="flex items-center">
                            <select
                                value={model}
                                onChange={(e) => setModel(e.target.value)}
                                className="border border-gray-300 rounded-lg px-4 py-3 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                            >
                                <option value="gpt-4o-mini">gpt-4o-mini</option>
                                <option value="gpt-5-nano">gpt-5-nano</option>
                                <option value="gpt-5-mini">gpt-5-mini</option>
                            </select>
                        </div>
                    </form>
                </div>
            </div>
        </div >
    );
}
