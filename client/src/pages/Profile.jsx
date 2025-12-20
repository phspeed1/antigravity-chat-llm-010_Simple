import React from 'react';
import { useAuth } from '../AuthContext';

export default function Profile() {
    const { user, logout } = useAuth();

    if (!user) return <div>Loading...</div>;

    return (
        <div className="min-h-screen bg-gray-50 p-8">
            <div className="max-w-2xl mx-auto bg-white rounded-lg shadow overflow-hidden">
                <div className="p-6">
                    <div className="flex items-center space-x-4">
                        {user.avatar && (
                            <img src={user.avatar} alt={user.name} className="h-16 w-16 rounded-full" />
                        )}
                        <div>
                            <h2 className="text-2xl font-bold text-gray-900">{user.name}</h2>
                            <p className="text-gray-500">{user.email}</p>
                        </div>
                    </div>
                </div>
                <div className="bg-gray-50 px-6 py-4 border-t border-gray-200">
                    <dl className="grid grid-cols-1 gap-x-4 gap-y-6 sm:grid-cols-2">
                        <div>
                            <dt className="text-sm font-medium text-gray-500">User ID</dt>
                            <dd className="mt-1 text-sm text-gray-900">{user.id}</dd>
                        </div>
                        <div>
                            <dt className="text-sm font-medium text-gray-500">Google ID</dt>
                            <dd className="mt-1 text-sm text-gray-900">{user.googleId}</dd>
                        </div>
                    </dl>
                </div>
                <div className="px-6 py-4 bg-gray-100 border-t border-gray-200">
                    <button
                        onClick={logout}
                        className="w-full inline-flex justify-center py-2 px-4 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
                    >
                        Sign out
                    </button>
                </div>
            </div>
        </div>
    );
}
