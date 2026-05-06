<script setup lang="ts">
import { computed, onMounted } from "vue";
import { useRoute } from "vue-router";
import { ElMessage } from "element-plus";

import { http } from "../api/client";
import LeaderboardBar from "../components/LeaderboardBar.vue";
import { useRoomStore } from "../stores/room";

const route = useRoute();
const store = useRoomStore();
const roomCode = computed(() => String(route.params.roomCode || ""));

const phaseText = computed(() => {
  const map: Record<string, string> = {
    ROUND_SPEAKING: "发言阶段",
    ROUND_VOTING: "投票阶段",
    ROUND_TIE_BREAK: "平票加赛发言",
    ROUND_GUESSING: "猜词阶段",
    ROUND_RESULT: "本轮结果",
    GAME_FINISHED: "游戏结束",
  };
  return map[store.phase] || store.phase;
});

function nicknameOf(pid: number) {
  const p = store.players.find((x: any) => x.id === pid);
  return p ? p.nickname : `#${pid}`;
}

async function nextPhase() {
  if (!store.gameId) return;
  try {
    const res = await http.post(
      `/api/games/${store.gameId}/rounds/${store.roundNo}/phase/next`,
      null,
      { headers: { "X-Host-Secret": store.hostSecret } }
    );
    ElMessage.success(`阶段已推进: ${res.data.phase}`);
    await store.fetchSnapshot(roomCode.value);
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail?.message || "推进失败");
  }
}

async function nextRandom() {
  if (!store.gameId) return;
  try {
    const res = await http.post(
      `/api/games/${store.gameId}/rounds/${store.roundNo}/speaking/next-random`,
      null,
      { headers: { "X-Host-Secret": store.hostSecret } }
    );
    if (res.data.player_id) {
      ElMessage.success(`随机到: ${nicknameOf(res.data.player_id)}`);
    }
    if (res.data.completed) {
      ElMessage.success("全员发言完成，已进入投票阶段");
    }
    await store.fetchSnapshot(roomCode.value);
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail?.message || "点名失败");
  }
}

async function nextSeq() {
  if (!store.gameId) return;
  try {
    const res = await http.post(
      `/api/games/${store.gameId}/rounds/${store.roundNo}/speaking/next-seq`,
      null,
      { headers: { "X-Host-Secret": store.hostSecret } }
    );
    if (res.data.player_id) {
      ElMessage.success(`顺序到: ${nicknameOf(res.data.player_id)}`);
    }
    if (res.data.completed) {
      ElMessage.success("全员发言完成，已进入投票阶段");
    }
    await store.fetchSnapshot(roomCode.value);
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail?.message || "点名失败");
  }
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

function voteTargetOf(row: any): string {
  if (row.votedTargetId == null) return "未投票";
  return `→ ${nicknameOf(row.votedTargetId)}`;
}

async function finishGame() {
  if (!store.gameId) return;
  try {
    await http.post(`/api/games/${store.gameId}/finish`, null, {
      headers: { "X-Host-Secret": store.hostSecret },
    });
    ElMessage.info("游戏已结束");
    await store.fetchSnapshot(roomCode.value);
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail?.message || "结束失败");
  }
}

async function restartGame() {
  if (!store.gameId) return;
  try {
    const res = await http.post(`/api/games/${store.gameId}/restart`, null, {
      headers: { "X-Host-Secret": store.hostSecret },
    });
    store.gameId = res.data.gameId;
    await store.fetchSnapshot(roomCode.value);
    ElMessage.success("已重新开始新一局");
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail?.message || "重开失败");
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
      <p>房间：{{ roomCode }} | 轮次：{{ store.roundNo }}</p>
      <p>
        当前阶段：<strong>{{ phaseText }}</strong>
      </p>
      <p v-if="store.phase === 'ROUND_TIE_BREAK'" style="color: #e6a23c">
        平票加赛中，只有平票玩家补充发言
      </p>

      <div
        style="display: flex; gap: 8px; flex-wrap: wrap; margin: 12px 0"
      >
        <el-button
          v-if="store.phase === 'ROUND_SPEAKING' || store.phase === 'ROUND_TIE_BREAK'"
          type="primary"
          @click="nextRandom"
          >随机点名</el-button
        >
        <el-button
          v-if="store.phase === 'ROUND_SPEAKING' || store.phase === 'ROUND_TIE_BREAK'"
          @click="nextSeq"
          >顺序点名</el-button
        >
        <el-button
          v-if="store.phase !== 'GAME_FINISHED'"
          type="warning"
          @click="nextPhase"
          >推进阶段</el-button
        >
        <el-button
          v-if="store.phase !== 'GAME_FINISHED'"
          type="danger"
          @click="finishGame"
          >结束游戏</el-button
        >
        <el-button
          v-if="store.phase === 'GAME_FINISHED'"
          type="success"
          @click="restartGame"
          >重新开始</el-button
        >
      </div>

      <p v-if="(store as any).game?.winnerSide">
        胜方：{{ (store as any).game?.winnerSide }}
      </p>

      <el-table :data="store.players" stripe :row-class-name="rowClassName">
        <el-table-column prop="seatNo" label="座位" width="60" />
        <el-table-column prop="nickname" label="昵称" />
        <el-table-column label="身份">
          <template #default="s">{{ roleText(s.row.role) }}</template>
        </el-table-column>
        <el-table-column label="发言" width="80">
          <template #default="s">{{
            s.row.spoken ? "已发言" : "未发言"
          }}</template>
        </el-table-column>
        <el-table-column label="投票" width="120">
          <template #default="s">
            <span v-if="s.row.eliminated">-</span>
            <span v-else-if="s.row.votedTargetId != null" style="color: #67c23a">
              {{ nicknameOf(s.row.votedTargetId) }}
            </span>
            <span v-else style="color: #909399">未投票</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="60">
          <template #default="s">{{
            s.row.eliminated ? "出局" : "存活"
          }}</template>
        </el-table-column>
      </el-table>
    </div>
    <LeaderboardBar />
  </div>
</template>
