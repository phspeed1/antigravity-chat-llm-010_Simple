import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../AuthContext';
import UploadModal from './UploadModal';

export default function Navigation() {
    const { user, logout } = useAuth();
    const [uploadModalOpen, setUploadModalOpen] = useState(false);

    if (!user) {
        return (
            <header className="bg-white shadow-sm border-b z-20 relative">
                <div className="max-w-7xl mx-auto px-4 py-4 sm:px-6 lg:px-8">
                    <h1 className="text-xl font-bold text-indigo-600 tracking-tight">Robin's LLM/RAG/Agent Lab</h1>
                </div>
            </header>
        );
    }

    return (
        <>
            <header className="bg-white shadow-sm border-b z-20 relative">
                <div className="max-w-7xl mx-auto px-4 py-4 sm:px-6 lg:px-8 flex justify-between items-center">
                    <h1 className="text-xl font-bold text-indigo-600 tracking-tight">Robin's LLM/RAG/Agent Lab</h1>

                    <nav className="flex items-center space-x-3">
                        <Link
                            to="/chat"
                            className="bg-white border border-gray-300 shadow-sm hover:bg-gray-50 text-gray-700 px-4 py-2 rounded-md text-sm font-medium transition-all cursor-pointer"
                        >
                            Chat
                        </Link>
                        <Link
                            to="/materials"
                            className="bg-white border border-gray-300 shadow-sm hover:bg-gray-50 text-gray-700 px-4 py-2 rounded-md text-sm font-medium transition-all cursor-pointer"
                        >
                            Materials
                        </Link>
                        <Link
                            to="/profile"
                            className="bg-white border border-gray-300 shadow-sm hover:bg-gray-50 text-gray-700 px-4 py-2 rounded-md text-sm font-medium transition-all cursor-pointer"
                        >
                            Profile
                        </Link>
                        <button
                            onClick={() => setUploadModalOpen(true)}
                            className="bg-white border border-gray-300 shadow-sm hover:bg-gray-50 text-gray-700 px-4 py-2 rounded-md text-sm font-medium transition-all cursor-pointer"
                        >
                            Upload
                        </button>
                        <button
                            onClick={logout}
                            className="bg-white border border-gray-300 shadow-sm hover:bg-red-50 text-red-600 px-4 py-2 rounded-md text-sm font-medium transition-all cursor-pointer"
                        >
                            Sign Out
                        </button>
                    </nav>
                </div>
            </header>

            {uploadModalOpen && <UploadModal isOpen={uploadModalOpen} onClose={() => setUploadModalOpen(false)} />}
        </>
    );
}
