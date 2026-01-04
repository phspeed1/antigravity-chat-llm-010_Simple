import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './AuthContext';
import Login from './pages/Login';
import Profile from './pages/Profile';
import Chat from './pages/Chat';
import Materials from './pages/Materials';
import AuthCallback from './AuthCallback';
import Navigation from './components/Navigation';

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
          <Navigation />
          <div className="flex-1 overflow-hidden relative">
            <Routes>
              <Route
                path="/materials"
                element={
                  <PrivateRoute>
                    <Materials />
                  </PrivateRoute>
                }
              />
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
              <Route path="*" element={<div className="p-4">404 - Page Not Found</div>} />
            </Routes>
          </div>
        </div>
      </Router>
    </AuthProvider>
  );
}

export default App

