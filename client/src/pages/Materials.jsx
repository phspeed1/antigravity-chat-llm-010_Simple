import React, { useState, useEffect } from 'react';
import { useAuth } from '../AuthContext';


export default function Materials() {
    const { user, logout } = useAuth();
    const [documents, setDocuments] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    const API_BASE_URL = window.location.hostname === 'localhost'
        ? 'http://localhost:8000'
        : '/llm';

    useEffect(() => {
        fetchAllDocuments();
    }, []);

    // Polling for analyzing documents
    useEffect(() => {
        const analyzingDocs = documents.some(doc => doc.status === 'analyzing');
        if (analyzingDocs) {
            const interval = setInterval(() => {
                fetchAllDocuments();
            }, 3000); // Poll every 3 seconds
            return () => clearInterval(interval);
        }
    }, [documents]);

    const fetchAllDocuments = async () => {
        try {
            setError(null);
            const token = localStorage.getItem('token');
            const res = await fetch(`${API_BASE_URL}/documents/all`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (res.ok) {
                const data = await res.json();
                setDocuments(data);
            } else {
                setError(`Failed to fetch: ${res.status} ${res.statusText}`);
            }
        } catch (error) {
            console.error('Error fetching documents:', error);
            setError(`Error: ${error.message}`);
        } finally {
            setLoading(false);
        }
    };

    const handleDelete = async (docId, filename) => {
        if (!window.confirm(`Are you sure you want to delete "${filename}"?`)) return;

        try {
            const token = localStorage.getItem('token');
            const res = await fetch(`${API_BASE_URL}/documents/${docId}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (res.ok) {
                setDocuments(prev => prev.filter(d => d.id !== docId));
            } else {
                alert('Failed to delete document');
            }
        } catch (error) {
            console.error('Error deleting document:', error);
            alert('Error deleting document');
        }
    };

    const handleAnalyze = async (docId, filename, status) => {
        if (status === 'analyzing' || status === 'completed') {
            alert(`Document is already ${status}`);
            return;
        }

        if (!window.confirm(`Analyze "${filename}"? This will process the document for RAG.`)) return;

        try {
            const token = localStorage.getItem('token');
            const res = await fetch(`${API_BASE_URL}/documents/${docId}/analyze`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (res.ok) {
                // Optimistically update status to analyzing
                setDocuments(prev => prev.map(d =>
                    d.id === docId ? { ...d, status: 'analyzing' } : d
                ));
            } else {
                const err = await res.json();
                alert(`Failed to start analysis: ${err.detail}`);
            }
        } catch (error) {
            console.error('Error starting analysis:', error);
            alert('Error starting analysis');
        }
    };

    return (
        <div className="h-full overflow-y-auto bg-gray-100 flex flex-col">
            {/* Global Header (Optional if App.jsx handles it, but creating consistency) */}
            {/* Assuming App.jsx has the header or we can just have a simple page header here */}

            <div className="max-w-7xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-8">
                <div className="flex justify-between items-center mb-6">
                    <h1 className="text-2xl font-bold text-gray-900">Materials (Common Knowledge Base)</h1>
                </div>

                {error && (
                    <div className="mb-4 p-4 bg-red-100 border border-red-400 text-red-700 rounded">
                        {error}
                    </div>
                )}

                <div className="bg-white shadow overflow-hidden rounded-lg">
                    {loading ? (
                        <div className="p-8 text-center text-gray-500">Loading documents...</div>
                    ) : !Array.isArray(documents) || documents.length === 0 ? (
                        <div className="p-8 text-center text-gray-500">No documents found. Upload text/pdf files in Chat to see them here.</div>
                    ) : (
                        <table className="min-w-full divide-y divide-gray-200">
                            <thead className="bg-gray-50">
                                <tr>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Date</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Filename</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                                </tr>
                            </thead>
                            <tbody className="bg-white divide-y divide-gray-200">
                                {documents.map((doc) => (
                                    <tr key={doc.id}>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                            {new Date(doc.createdAt).toLocaleDateString()} {new Date(doc.createdAt).toLocaleTimeString()}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                                            {doc.filename}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap">
                                            <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full 
                                                ${doc.status === 'completed' ? 'bg-green-100 text-green-800' :
                                                    doc.status === 'analyzing' ? 'bg-yellow-100 text-yellow-800' :
                                                        doc.status === 'error' ? 'bg-red-100 text-red-800' :
                                                            'bg-gray-100 text-gray-800'}`}>
                                                {doc.status}
                                            </span>
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 space-x-2">
                                            <button
                                                onClick={() => handleAnalyze(doc.id, doc.filename, doc.status)}
                                                className={`px-3 py-1 rounded text-xs font-medium transition-colors shadow-sm cursor-pointer
                                                    ${(doc.status === 'analyzing' || doc.status === 'completed')
                                                        ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                                                        : 'bg-indigo-600 text-white hover:bg-indigo-700'}`}
                                                disabled={doc.status === 'analyzing' || doc.status === 'completed'}
                                            >
                                                {doc.status === 'completed' ? 'Done' : doc.status === 'analyzing' ? 'Processing' : 'Analyze'}
                                            </button>
                                            <button
                                                onClick={() => handleDelete(doc.id, doc.filename)}
                                                className="px-3 py-1 bg-white border border-gray-300 text-red-600 rounded hover:bg-gray-50 text-xs font-medium transition-colors shadow-sm cursor-pointer"
                                            >
                                                Delete
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    )}
                </div>
            </div>
        </div>
    );
}
