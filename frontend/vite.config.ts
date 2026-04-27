import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vitejs.dev/config/
export default defineConfig({
    // Load env files from the project root so VITE_* vars defined in
    // /home/mukan/Documents/Inzyts/.env (alongside backend env) are picked
    // up automatically. Without this, Vite only reads frontend/.env*.
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
