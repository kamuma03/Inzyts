import React, { useEffect } from 'react';
import { X, CheckCircle, AlertCircle, Info, AlertTriangle } from 'lucide-react';

export type ToastType = 'success' | 'error' | 'info' | 'warning';

export interface ToastProps {
    id: string;
    message: string;
    type: ToastType;
    onClose: (id: string) => void;
    duration?: number;
}

export const Toast: React.FC<ToastProps> = ({ id, message, type, onClose, duration = 5000 }) => {
    useEffect(() => {
        const timer = setTimeout(() => {
            onClose(id);
        }, duration);
        return () => clearTimeout(timer);
    }, [id, duration, onClose]);

    const getIcon = () => {
        switch (type) {
            case 'success': return <CheckCircle size={20} />;
            case 'error': return <AlertCircle size={20} />;
            case 'warning': return <AlertTriangle size={20} />;
            default: return <Info size={20} />;
        }
    };

    const getTypeClasses = () => {
        switch (type) {
            case 'success': return 'border-[rgba(72,187,120,0.4)] bg-[rgba(72,187,120,0.15)]';
            case 'error': return 'border-[rgba(245,101,101,0.4)] bg-[rgba(245,101,101,0.15)]';
            case 'warning': return 'border-[rgba(237,137,54,0.4)] bg-[rgba(237,137,54,0.15)]';
            default: return 'border-[rgba(66,153,225,0.4)] bg-[rgba(66,153,225,0.15)]';
        }
    };

    const getIconColor = () => {
        switch (type) {
            case 'success': return '#68d391';
            case 'error': return '#fc8181';
            case 'warning': return '#ed8936';
            default: return '#4cc9f0';
        }
    };

    return (
        <div
            className={`flex items-center gap-3 px-4 py-3 rounded-lg shadow-[0_8px_16px_rgba(0,0,0,0.4)] border min-w-[300px] max-w-[420px] backdrop-blur-[12px] animate-[slideIn_0.3s_ease-out] z-[1000] ${getTypeClasses()}`}
            role="alert"
            aria-live="polite"
            aria-atomic="true"
        >
            {React.cloneElement(getIcon(), { color: getIconColor() })}
            <p className="flex-1 m-0 text-sm font-medium text-[var(--text-primary)]">{message}</p>
            <button
                onClick={() => onClose(id)}
                className="bg-transparent border-none cursor-pointer text-[#a0aec0] p-0 flex"
                aria-label="Close"
            >
                <X size={16} />
            </button>
        </div>
    );
};
