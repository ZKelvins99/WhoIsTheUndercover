import { defineStore } from "pinia";
import { http, wsBase } from "../api/client";

function setCookie(name: string, value: string, days = 30) {
  const d = new Date();
  d.setTime(d.getTime() + days * 86400000);
  document.cookie = `${name}=${encodeURIComponent(value)};expires=${d.toUTCString()};path=/;SameSite=Lax`;
}

function getCookie(name: string): string {
  const match = document.cookie.match(new RegExp("(^| )" + name + "=([^;]+)"));
  return match ? decodeURIComponent(match[2]) : "";
}

let speakerNoticeTimer: ReturnType<typeof setTimeout> | null = null;

export type BoardItem = {
  playerId: number;
  nickname: string;
  totalScore: number;
  survivalRounds: number;
  hitVotes: number;
  joinOrder: number;
};

export const useRoomStore = defineStore("room", {
  state: () => ({
    roomCode: "",
    hostSecret: getCookie("host_secret"),
    playerToken: getCookie("player_token"),
    playerId: Number(getCookie("player_id") || 0),
    gameId: 0,
    game: null as any,
    phase: "LOBBY",
    roundNo: 0,
    players: [] as any[],
    leaderboard: [] as BoardItem[],
    ws: null as WebSocket | null,
    wsRetryCount: 0,
    wsManualClose: false,
    lastEvent: "",
    currentSpeakerId: 0,
    speakerNotice: "",
    speakerDialogVisible: false,
  }),
  actions: {
    setHostSecret(v: string) {
      this.hostSecret = v;
      setCookie("host_secret", v);
    },
    setPlayerToken(v: string, playerId?: number) {
      this.playerToken = v;
      setCookie("player_token", v);
      if (playerId) {
        this.playerId = playerId;
        setCookie("player_id", String(playerId));
      }
    },
    async fetchSnapshot(roomCode: string) {
      this.roomCode = roomCode;
      const res = await http.get(`/api/rooms/${roomCode}/snapshot`, {
        headers: {
          "X-Host-Secret": this.hostSecret || undefined,
          "X-Player-Token": this.playerToken || undefined,
        },
      });
      this.players = res.data.players || [];
      this.leaderboard = res.data.leaderboard || [];
      this.game = res.data.game || null;
      if (res.data.game) {
        this.gameId = res.data.game.id;
        this.phase = res.data.game.phase;
        this.roundNo = res.data.game.roundNo;
      } else {
        this.gameId = 0;
        this.phase = "LOBBY";
        this.roundNo = 0;
      }
    },
    connectWS(roomCode: string) {
      this.wsManualClose = false;
      if (this.ws) {
        this.ws.close();
      }
      const ws = new WebSocket(`${wsBase()}/ws/rooms/${roomCode}`);
      ws.onopen = () => {
        this.wsRetryCount = 0;
      };
      ws.onmessage = (evt) => {
        const payload = JSON.parse(evt.data);
        this.lastEvent = payload.event;

        // Ignore heartbeat responses
        if (payload.event === "heartbeat.ping") return;

        if (payload.event === "round.speaker_selected") {
          const pid = Number(payload?.data?.playerId || 0);
          if (pid > 0) {
            this.currentSpeakerId = pid;
            const speaker = this.players.find((p: any) => p.id === pid);
            const name = speaker ? speaker.nickname : `${pid}号`;
            this.speakerNotice = `请 ${name} 发言`;
            this.speakerDialogVisible = true;
            if (speakerNoticeTimer) {
              clearTimeout(speakerNoticeTimer);
            }
            speakerNoticeTimer = setTimeout(() => {
              this.currentSpeakerId = 0;
              this.speakerNotice = "";
              this.speakerDialogVisible = false;
            }, 3000);
          }
        }

        this.fetchSnapshot(roomCode);
      };
      ws.onclose = () => {
        this.ws = null;
        // Auto-reconnect with exponential backoff (max 10s) unless manually closed
        if (!this.wsManualClose && this.roomCode) {
          const delay = Math.min(1000 * Math.pow(2, this.wsRetryCount), 10000);
          this.wsRetryCount++;
          setTimeout(() => {
            if (!this.wsManualClose && this.roomCode && !this.ws) {
              this.connectWS(roomCode);
            }
          }, delay);
        }
      };
      ws.onerror = () => {
        ws.close();
      };
      this.ws = ws;
    },
    disconnectWS() {
      this.wsManualClose = true;
      if (this.ws) {
        this.ws.close();
        this.ws = null;
      }
    },
  },
});
