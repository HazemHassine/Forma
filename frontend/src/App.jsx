import { useState, createContext, useContext, useCallback } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import EditorPage from './pages/EditorPage';
import VersionsPage from './pages/VersionsPage';
import JobsPage from './pages/JobsPage';
import OptimizePage from './pages/OptimizePage';
import CoverLettersPage from './pages/CoverLettersPage';
import CompanyResearchPage from './pages/CompanyResearchPage';
import Toast from './components/Toast';

const ToastContext = createContext(null);
const AIProviderContext = createContext(null);
const AI_PROVIDER_STORAGE_KEY = 'forma.aiProvider';
const AI_PROVIDERS = new Set(['gemini', 'chatgpt']);

function readableToastMessage(message) {
  if (typeof message === 'string') return message;
  if (message instanceof Error) return message.message;
  if (message?.message) return String(message.message);

  try {
    return JSON.stringify(message);
  } catch {
    return 'Something went wrong';
  }
}

// The toast hook is shared by page components.
// eslint-disable-next-line react-refresh/only-export-components
export function useToast() {
  return useContext(ToastContext);
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAIProvider() {
  const context = useContext(AIProviderContext);
  if (!context) throw new Error('useAIProvider must be used inside App');
  return context;
}

function App() {
  const [toasts, setToasts] = useState([]);
  const [aiProvider, setAIProviderState] = useState(() => {
    const saved = localStorage.getItem(AI_PROVIDER_STORAGE_KEY);
    return AI_PROVIDERS.has(saved) ? saved : 'gemini';
  });

  const setAIProvider = useCallback((provider) => {
    if (!AI_PROVIDERS.has(provider)) return;
    localStorage.setItem(AI_PROVIDER_STORAGE_KEY, provider);
    setAIProviderState(provider);
  }, []);

  const addToast = useCallback((message, type = 'info') => {
    const id = Date.now() + Math.random();
    setToasts(prev => [
      ...prev,
      { id, message: readableToastMessage(message), type },
    ]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 3500);
  }, []);

  const removeToast = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={addToast}>
      <AIProviderContext.Provider value={{ aiProvider, setAIProvider }}>
        <Layout>
          <Routes>
            <Route path="/" element={<Navigate to="/editor" replace />} />
            <Route path="/editor" element={<EditorPage />} />
            <Route path="/editor/:id" element={<EditorPage />} />
            <Route path="/versions" element={<VersionsPage />} />
            <Route path="/jobs" element={<JobsPage />} />
            <Route path="/optimize" element={<OptimizePage />} />
            <Route path="/cover-letters" element={<CoverLettersPage />} />
            <Route path="/company-research" element={<CompanyResearchPage />} />
          </Routes>
        </Layout>
        <Toast toasts={toasts} onRemove={removeToast} />
      </AIProviderContext.Provider>
    </ToastContext.Provider>
  );
}

export default App;
