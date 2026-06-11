import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vitejs.dev/config/
export default defineConfig({
    // Load env files from the project root so VITE_* vars defined in
    // /home/mukan/Documents/Inzyts/.env (alongside backend env) are picked
    // up automatically. Without this, Vite only reads frontend/.env*.
    //
    // SECURITY WARNING: this points at the SAME .env the backend uses, and
    // Vite inlines every VITE_-prefixed var into the client bundle (publicly
    // readable). Therefore NO secret (API keys, DB URIs, JWT secrets, etc.)
    // may ever be given a VITE_ prefix in that shared .env — only truly public
    // config (e.g. VITE_API_URL) belongs there. Non-prefixed vars stay
    // server-only and are safe.
    envDir: '..',
    plugins: [
        react(),
        tailwindcss(),
    ],
    resolve: {
        alias: {
            'react-window': 'react-window/dist/react-window.cjs'
        }
    },
    server: {
        host: true, // Listen on all addresses
        proxy: {
            '/api': {
                target: process.env.BACKEND_URL || 'http://backend:8000',
                changeOrigin: true,
                secure: false,
            },
            '/socket.io': {
                target: process.env.BACKEND_URL || 'http://backend:8000',
                ws: true,
            }
        }
    }
})
