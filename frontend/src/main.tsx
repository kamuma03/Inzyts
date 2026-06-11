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
    // Build the fallback with the DOM API + textContent so the error value is
    // never interpolated as HTML (avoids XSS if it ever carries markup).
    const container = document.createElement('div');
    container.style.padding = '20px';
    container.style.color = 'red';
    const heading = document.createElement('h1');
    heading.textContent = 'Fatal Boot Error';
    const pre = document.createElement('pre');
    pre.textContent = error instanceof Error ? error.message : String(error);
    container.append(heading, pre);
    document.body.replaceChildren(container);
}
