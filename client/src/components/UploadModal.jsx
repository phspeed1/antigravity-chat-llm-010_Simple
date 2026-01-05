import React, { useState, useEffect, useRef } from 'react';

export default function UploadModal({ isOpen, onClose }) {
    const [file, setFile] = useState(null);
    const [uploading, setUploading] = useState(false);
    const [documents, setDocuments] = useState([]);
    const [message, setMessage] = useState('');
    const fileInputRef = useRef(null);

    useEffect(() => {
        if (isOpen) {
            fetchDocuments();
            setMessage('');
            setFile(null);
        }
    }, [isOpen]);

    const fetchDocuments = async () => {
        try {
            const token = localStorage.getItem('token');
            const res = await fetch('http://localhost:8000/documents', {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (res.ok) {
                const data = await res.json();
                setDocuments(data);
            }
        } catch (error) {
            console.error('Error fetching documents:', error);
        }
    };

    const handleFileChange = (e) => {
        if (e.target.files && e.target.files[0]) {
            setFile(e.target.files[0]);
            setMessage('');
        }
    };

    const handleUpload = async () => {
        if (!file) return;
        setUploading(true);
        setMessage('');

        const formData = new FormData();
        formData.append('file', file);

        try {
            const token = localStorage.getItem('token');
            const res = await fetch('http://localhost:8000/documents/upload', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`
                },
                body: formData
            });

            if (res.ok) {
                setMessage('Upload successful!');
                setFile(null);
                if (fileInputRef.current) fileInputRef.current.value = '';
                fetchDocuments();
            } else {
                const err = await res.json();
                setMessage(`Error: ${err.detail || 'Upload failed'}`);
            }
        } catch (error) {
            console.error('Error uploading:', error);
            setMessage(`Error: ${error.message}`);
        } finally {
            setUploading(false);
        }
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white rounded-lg p-6 w-full max-w-lg mx-4">
                <div className="flex justify-between items-center mb-4">
                    <h2 className="text-xl font-bold text-gray-800">Knowledge Base</h2>
                    <button onClick={onClose} className="text-gray-500 hover:text-gray-700">
                        ✕
                    </button>
                </div>

                {/* Upload Section */}
                <div className="mb-6 p-4 bg-gray-50 rounded-lg border border-dashed border-gray-300">
                    <div className="flex flex-col gap-2">
                        <label className="block text-sm font-medium text-gray-700">Upload Document</label>
                        <div className="flex gap-2">
                            <input
                                type="file"
                                ref={fileInputRef}
                                onChange={handleFileChange}
                                className="block w-full text-sm text-gray-500
                                    file:mr-4 file:py-2 file:px-4
                                    file:rounded-md file:border-0
                                    file:text-sm file:font-semibold
                                    file:bg-indigo-50 file:text-indigo-700
                                    hover:file:bg-indigo-100 file:cursor-pointer cursor-pointer"
                            />
                            <button
                                onClick={handleUpload}
                                disabled={!file || uploading}
                                className={`px-4 py-2 bg-indigo-600 text-white rounded-md font-medium text-sm
                                    ${(!file || uploading) ? 'opacity-50 cursor-not-allowed' : 'hover:bg-indigo-700 cursor-pointer'}`}
                            >
                                {uploading ? 'Adding...' : 'Add File'}
                            </button>
                        </div>
                        {message && (
                            <p className={`text-sm ${message.startsWith('Error') ? 'text-red-500' : 'text-green-500'}`}>
                                {message}
                            </p>
                        )}
                    </div>
                </div>

                {/* Document List */}
                <div>
                    <h3 className="text-md font-semibold text-gray-700 mb-2">Your Documents</h3>
                    <div className="max-h-60 overflow-y-auto border rounded-md">
                        {!Array.isArray(documents) || documents.length === 0 ? (
                            <p className="p-4 text-center text-gray-500 text-sm">No documents uploaded yet.</p>
                        ) : (
                            <table className="min-w-full divide-y divide-gray-200">
                                <thead className="bg-gray-50">
                                    <tr>
                                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Filename</th>
                                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Date</th>
                                    </tr>
                                </thead>
                                <tbody className="bg-white divide-y divide-gray-200">
                                    {documents.map((doc) => (
                                        <tr key={doc.id}>
                                            <td className="px-4 py-2 text-sm text-gray-900 truncate max-w-[150px]" title={doc.filename}>
                                                {doc.filename}
                                            </td>
                                            <td className="px-4 py-2 text-sm">
                                                <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full 
                                                    ${doc.status === 'completed' ? 'bg-green-100 text-green-800' :
                                                        doc.status === 'analyzing' ? 'bg-yellow-100 text-yellow-800' :
                                                            doc.status === 'error' ? 'bg-red-100 text-red-800' :
                                                                'bg-gray-100 text-gray-800'}`}>
                                                    {doc.status}
                                                </span>
                                            </td>
                                            <td className="px-4 py-2 text-sm text-gray-500">
                                                {new Date(doc.createdAt).toLocaleDateString()}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
