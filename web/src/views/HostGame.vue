<script setup lang="ts">
import { computed, onMounted } from "vue";
import { ref } from "vue";
import { useRoute } from "vue-router";
import { ElMessage } from "element-plus";

import { http } from "../api/client";
import LeaderboardBar from "../components/LeaderboardBar.vue";
import { useRoomStore } from "../stores/room";

const route = useRoute();
const store = useRoomStore();
const roomCode = computed(() => String(route.params.roomCode || ""));
const speechBonusIds = ref<number[]>([]);
const logicBonusIds = ref<number[]>([]);
const applyingBonus = ref(false);

async function nextPhase() {
  if (!store.gameId) return;
  await http.post(
    `/api/games/${store.gameId}/rounds/${store.roundNo}/phase/next`,
    null,
    { headers: { "X-Host-Secret": store.hostSecret } }
  );
  await store.fetchSnapshot(roomCode.value);
}

async function nextRandom() {
  if (!store.gameId) return;
  const res = await http.post(
    `/api/games/${store.gameId}/rounds/${store.roundNo}/speaking/next-random`,
    null,
    { headers: { "X-Host-Secret": store.hostSecret } }
  );
  if (res.data.player_id) {
    ElMessage.success(`随机到玩家 ${res.data.player_id}`);
  }
  if (res.data.completed) {
    ElMessage.success("本轮发言完成，已自动进入投票阶段");
  }
  await store.fetchSnapshot(roomCode.value);
}

async function nextSeq() {
  if (!store.gameId) return;
  const res = await http.post(
    `/api/games/${store.gameId}/rounds/${store.roundNo}/speaking/next-seq`,
    null,
    { headers: { "X-Host-Secret": store.hostSecret } }
  );
  if (res.data.player_id) {
    ElMessage.success(`顺序到玩家 ${res.data.player_id}`);
  }
  if (res.data.completed) {
    ElMessage.success("本轮发言完成，已自动进入投票阶段");
  }
  await store.fetchSnapshot(roomCode.value);
}

function rowClassName({ row }: { row: any }) {
  if (row.id === store.currentSpeakerId) return "row-current-speaker";
  if (row.eliminated) return "row-eliminated";
  if (row.spoken) return "row-spoken";
  return "";
}

function roleText(role?: string | null) {
  if (!role) return "";
  if (role === "CIVILIAN") return "平民";
  if (role === "UNDERCOVER") return "卧底";
  if (role === "BLANK") return "白板";
  return role;
}

async function finishGame() {
  if (!store.gameId) return;
  await http.post(`/api/games/${store.gameId}/finish`, null, {
    headers: { "X-Host-Secret": store.hostSecret },
  });
  await store.fetchSnapshot(roomCode.value);
}

async function restartGame() {
  if (!store.gameId) return;
  const res = await http.post(`/api/games/${store.gameId}/restart`, null, {
    headers: { "X-Host-Secret": store.hostSecret },
  });
  store.gameId = res.data.gameId;
  await store.fetchSnapshot(roomCode.value);
  ElMessage.success("已重新开始新一局");
}

async function applyInteractionBonus() {
  if (!store.gameId) return;
  applyingBonus.value = true;
  try {
    await http.post(
      `/api/games/${store.gameId}/rounds/${store.roundNo}/interaction-bonus`,
      {
        speech_bonus_player_ids: speechBonusIds.value,
        logic_bonus_player_ids: logicBonusIds.value,
      },
      { headers: { "X-Host-Secret": store.hostSecret } }
    );
    ElMessage.success("互动加分已应用");
    await store.fetchSnapshot(roomCode.value);
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail?.message || "互动加分失败");
  } finally {
    applyingBonus.value = false;
  }
}

onMounted(async () => {
  store.connectWS(roomCode.value);
  await store.fetchSnapshot(roomCode.value);
});
</script>

<template>
  <div class="page" style="padding-bottom: 90px">
    <h1 class="page-title">主持人控制台</h1>
    <div class="panel">
      <el-alert
        v-if="store.speakerNotice"
        :title="store.speakerNotice"
        type="success"
        show-icon
        :closable="false"
        style="margin-bottom: 10px"
      />
      <p>房间：{{ roomCode }}</p>
      <p>游戏ID：{{ store.gameId }}</p>
      <p>当前阶段：{{ store.phase }} | 轮次：{{ store.roundNo }}</p>
      <div style="display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px">
        <el-button type="primary" @click="nextRandom">随机点名</el-button>
        <el-button @click="nextSeq">顺序点名</el-button>
        <el-button type="warning" @click="nextPhase">推进阶段</el-button>
        <el-button type="danger" @click="finishGame">结束游戏</el-button>
        <el-button v-if="store.phase === 'GAME_FINISHED'" type="success" @click="restartGame">重新开始</el-button>
      </div>

      <div class="panel" style="margin-bottom: 12px">
        <div style="margin-bottom: 6px">互动加分（每类最多2人，每人每轮最多+2）</div>
        <div style="display: flex; gap: 8px; flex-wrap: wrap; align-items: center">
          <el-select v-model="speechBonusIds" multiple collapse-tags placeholder="高质量发言 +1" style="min-width: 240px">
            <el-option
              v-for="p in store.players"
              :key="`speech-${p.id}`"
              :label="`#${p.seatNo} ${p.nickname}`"
              :value="p.id"
              :disabled="p.eliminated"
            />
          </el-select>
          <el-select v-model="logicBonusIds" multiple collapse-tags placeholder="关键追问/逻辑 +1" style="min-width: 240px">
            <el-option
              v-for="p in store.players"
              :key="`logic-${p.id}`"
              :label="`#${p.seatNo} ${p.nickname}`"
              :value="p.id"
              :disabled="p.eliminated"
            />
          </el-select>
          <el-button type="primary" :loading="applyingBonus" @click="applyInteractionBonus">应用加分</el-button>
        </div>
      </div>

      <p v-if="(store as any).game?.winnerSide">胜方：{{ (store as any).game?.winnerSide }}</p>
      <el-table :data="store.players" stripe :row-class-name="rowClassName">
        <el-table-column prop="seatNo" label="座位" width="70" />
        <el-table-column prop="nickname" label="昵称" />
        <el-table-column label="身份(主持人可见)">
          <template #default="s">{{ roleText(s.row.role) }}</template>
        </el-table-column>
        <el-table-column prop="spoken" label="发言">
          <template #default="s">{{ s.row.spoken ? "已发言" : "未发言" }}</template>
        </el-table-column>
        <el-table-column prop="eliminated" label="状态">
          <template #default="s">{{ s.row.eliminated ? "出局" : "存活" }}</template>
        </el-table-column>
      </el-table>
    </div>
    <LeaderboardBar />
  </div>
</template>
