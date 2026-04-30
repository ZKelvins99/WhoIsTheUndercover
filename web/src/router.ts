import { createRouter, createWebHistory } from "vue-router";

import HostCreateRoom from "./views/HostCreateRoom.vue";
import HostRoom from "./views/HostRoom.vue";
import HostGame from "./views/HostGame.vue";
import PlayerJoin from "./views/PlayerJoin.vue";
import PlayerGame from "./views/PlayerGame.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", redirect: "/player/join" },
    { path: "/host/create", component: HostCreateRoom },
    { path: "/host/room/:roomCode", component: HostRoom },
    { path: "/host/game/:roomCode", component: HostGame },
    { path: "/player/join", component: PlayerJoin },
    { path: "/player/game/:roomCode", component: PlayerGame },
  ],
});

export default router;
