import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './AuthContext';
import Login from './pages/Login';
import Profile from './pages/Profile';
import Chat from './pages/Chat';
import AuthCallback from './AuthCallback';

function PrivateRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div>Loading...</div>;
  return user ? children : <Navigate to="/login" />;
}

function App() {
  return (
    <AuthProvider>
      <Router>
        <div className="flex flex-col h-screen bg-gray-50">
          <header className="bg-white shadow-sm border-b z-20 relative">
            <div className="max-w-7xl mx-auto px-4 py-4 sm:px-6 lg:px-8">
              <h1 className="text-xl font-bold text-indigo-600 tracking-tight">Robin's LLM/RAG/Agent Lab</h1>
            </div>
          </header>
          <div className="flex-1 overflow-hidden relative">
            <Routes>
              <Route path="/login" element={<Login />} />
              <Route path="/auth-callback" element={<AuthCallback />} />
              <Route
                path="/profile"
                element={
                  <PrivateRoute>
                    <Profile />
                  </PrivateRoute>
                }
              />
              <Route
                path="/chat"
                element={
                  <PrivateRoute>
                    <Chat />
                  </PrivateRoute>
                }
              />
              <Route path="/" element={<Navigate to="/chat" />} />
            </Routes>
          </div>
        </div>
      </Router>
    </AuthProvider>
  );
}

export default App

