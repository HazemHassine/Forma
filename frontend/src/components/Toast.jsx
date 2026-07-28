import { Check, X, Info, AlertTriangle } from 'lucide-react';
import './Toast.css';

const icons = {
  success: <Check size={16} />,
  error: <X size={16} />,
  info: <Info size={16} />,
  warning: <AlertTriangle size={16} />,
};

export default function Toast({ toasts, onRemove }) {
  if (!toasts.length) return null;

  return (
    <div className="toast-container">
      {toasts.map(toast => (
        <div key={toast.id} className={`toast ${toast.type}`}>
          <span className="toast-icon">{icons[toast.type] || icons.info}</span>
          <span className="toast-message">{toast.message}</span>
          <button className="toast-close" onClick={() => onRemove(toast.id)}><X size={14} /></button>
        </div>
      ))}
    </div>
  );
}
