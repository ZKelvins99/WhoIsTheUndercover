import { defineStore } from "pinia";
import { http, wsBase } from "../api/client";

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
    hostSecret: localStorage.getItem("host_secret") || "",
    playerToken: localStorage.getItem("player_token") || "",
    playerId: Number(localStorage.getItem("player_id") || 0),
    gameId: 0,
    game: null as any,
    phase: "LOBBY",
    roundNo: 0,
    players: [] as any[],
    leaderboard: [] as BoardItem[],
    ws: null as WebSocket | null,
    lastEvent: "",
    currentSpeakerId: 0,
    speakerNotice: "",
  }),
  actions: {
    setHostSecret(v: string) {
      this.hostSecret = v;
      localStorage.setItem("host_secret", v);
    },
    setPlayerToken(v: string, playerId?: number) {
      this.playerToken = v;
      localStorage.setItem("player_token", v);
      if (playerId) {
        this.playerId = playerId;
        localStorage.setItem("player_id", String(playerId));
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
      if (this.ws) {
        this.ws.close();
      }
      const ws = new WebSocket(`${wsBase()}/ws/rooms/${roomCode}`);
      ws.onmessage = (evt) => {
        const payload = JSON.parse(evt.data);
        this.lastEvent = payload.event;

        if (payload.event === "round.speaker_selected") {
          const pid = Number(payload?.data?.playerId || 0);
          if (pid > 0) {
            this.currentSpeakerId = pid;
            this.speakerNotice = `请 ${pid} 号玩家发言`;
            if (speakerNoticeTimer) {
              clearTimeout(speakerNoticeTimer);
            }
            speakerNoticeTimer = setTimeout(() => {
              this.currentSpeakerId = 0;
              this.speakerNotice = "";
            }, 5000);
          }
        }

        this.fetchSnapshot(roomCode);
      };
      this.ws = ws;
    },
    disconnectWS() {
      if (this.ws) {
        this.ws.close();
        this.ws = null;
      }
    },
  },
});
