import React, { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from './AuthContext';

export default function AuthCallback() {
    const [searchParams] = useSearchParams();
    const navigate = useNavigate();
    const { login } = useAuth();

    useEffect(() => {
        const token = searchParams.get('token');
        if (token) {
            // In a real app, you might want to fetch user data immediately or valid token
            login({ /* temp user data until fetch */ }, token);
            // Force reload or just navigate to trigger context check
            // For simplicity, we just navigate, and AuthContext checkAuth will run if we call it or if we trust the token and fetch user details there. 
            // Actually, AuthContext only calls checkAuth on mount.
            // We should reload to ensure AuthContext fetches fresh data.
            window.location.href = '/profile';
        } else {
            navigate('/login');
        }
    }, [searchParams, navigate, login]);

    return (
        <div className="flex items-center justify-center min-h-screen">
            Processing login...
        </div>
    );
}
