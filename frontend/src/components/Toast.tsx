import React, { useEffect } from 'react';
import { X, CheckCircle, AlertCircle, Info, AlertTriangle, type LucideIcon } from 'lucide-react';

export type ToastType = 'success' | 'error' | 'info' | 'warning';

export interface ToastProps {
    id: string;
    message: string;
    type: ToastType;
    onClose: (id: string) => void;
    duration?: number;
}

interface ToastVariant {
    Icon: LucideIcon;
    classes: string;
    color: string;
}

const TOAST_VARIANTS: Record<ToastType, ToastVariant> = {
    success: { Icon: CheckCircle,    classes: 'border-[rgba(72,187,120,0.4)] bg-[rgba(72,187,120,0.15)]', color: '#68d391' },
    error:   { Icon: AlertCircle,    classes: 'border-[rgba(245,101,101,0.4)] bg-[rgba(245,101,101,0.15)]', color: '#fc8181' },
    warning: { Icon: AlertTriangle,  classes: 'border-[rgba(237,137,54,0.4)] bg-[rgba(237,137,54,0.15)]', color: '#ed8936' },
    info:    { Icon: Info,           classes: 'border-[rgba(66,153,225,0.4)] bg-[rgba(66,153,225,0.15)]', color: '#4cc9f0' },
};

export const Toast: React.FC<ToastProps> = ({ id, message, type, onClose, duration = 5000 }) => {
    useEffect(() => {
        const timer = setTimeout(() => onClose(id), duration);
        return () => clearTimeout(timer);
    }, [id, duration, onClose]);

    const { Icon, classes, color } = TOAST_VARIANTS[type] ?? TOAST_VARIANTS.info;

    return (
        <div
            className={`flex items-center gap-3 px-4 py-3 rounded-lg shadow-[0_8px_16px_rgba(0,0,0,0.4)] border min-w-[300px] max-w-[420px] backdrop-blur-[12px] animate-[slideIn_0.3s_ease-out] z-[1000] ${classes}`}
            role="alert"
            aria-live="polite"
            aria-atomic="true"
        >
            <Icon size={20} color={color} />
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
