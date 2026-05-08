import axios from "axios";

const API_BASE = import.meta.env.VITE_API_BASE || "";

export const http = axios.create({
  baseURL: API_BASE,
  timeout: 15000,
});

export function wsBase(): string {
  if (import.meta.env.VITE_WS_BASE) {
    return import.meta.env.VITE_WS_BASE.replace(/\/$/, "");
  }
  const loc = window.location;
  const proto = loc.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${loc.host}`;
}
