import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// No GitHub Pages o site vive em /<nome-do-repo>/. O workflow define BASE_PATH.
export default defineConfig({
  base: process.env.BASE_PATH ?? '/',
  plugins: [react()],
})
