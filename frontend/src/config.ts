/**
 * Application configuration.
 *
 * VITE_API_URL controls which backend the frontend talks to.
 * - Local development: defaults to http://localhost:8000
 * - Production (Cloudflare Pages): set via environment variable
 */

export const API = import.meta.env.VITE_API_URL
  ? (import.meta.env.VITE_API_URL as string).replace(/\/+$/, '')
  : 'http://localhost:8000';
