import axios from "axios";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

export const http = axios.create({
  baseURL: API_BASE,
  timeout: 15000,
});

export function wsBase() {
  return (import.meta.env.VITE_WS_BASE || "ws://localhost:8000").replace(/\/$/, "");
}
