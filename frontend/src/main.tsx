import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

try {
    const rootElement = document.getElementById('root');
    if (!rootElement) throw new Error('Failed to find the root element');
    
    ReactDOM.createRoot(rootElement).render(
        <React.StrictMode>
            <App />
        </React.StrictMode>,
    );
} catch (error) {
    console.error("FATAL REACT BOOT ERROR:", error);
    document.body.innerHTML = `<div style="padding: 20px; color: red;"><h1>Fatal Boot Error</h1><pre>${error}</pre></div>`;
}
