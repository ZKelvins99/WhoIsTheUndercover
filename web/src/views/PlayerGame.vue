<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { ElMessage } from "element-plus";

import LeaderboardBar from "../components/LeaderboardBar.vue";
import { useRoomStore } from "../stores/room";
import { http } from "../api/client";

const route = useRoute();
const store = useRoomStore();
const roomCode = computed(() => String(route.params.roomCode || ""));
const voting = ref(false);
const selectedTargetId = ref<number | null>(null);
const guessing = ref(false);
const guessText = ref("");

const me = computed(() => store.players.find((p: any) => p.id === store.playerId) || null);
const myWord = computed(() => (store as any).game?.myWord || "");
const canVote = computed(
  () =>
    !!store.gameId &&
    (store.phase === "ROUND_VOTING" || store.phase === "ROUND_TIE_BREAK") &&
    !!me.value &&
    !me.value.eliminated &&
    !(store as any).game?.myVoteSubmitted
);
const canGuess = computed(
  () =>
    !!store.gameId &&
    store.phase === "ROUND_GUESSING" &&
    !!me.value &&
    !me.value.eliminated &&
    (((store as any).game?.myGuessUsed || 0) < ((store as any).game?.myGuessLimit || 0))
);

function roleText(role?: string | null) {
  if (!role) return "";
  if (role === "CIVILIAN") return "平民";
  if (role === "UNDERCOVER") return "卧底";
  if (role === "BLANK") return "白板";
  return role;
}

function rowClassName({ row }: { row: any }) {
  if (row.id === store.currentSpeakerId) return "row-current-speaker";
  if (row.eliminated) return "row-eliminated";
  if (row.spoken) return "row-spoken";
  return "";
}

async function submitVote() {
  if (!canVote.value) return;
  if (!selectedTargetId.value) {
    ElMessage.warning("请选择投票目标");
    return;
  }
  voting.value = true;
  try {
    await http.post(
      `/api/games/${store.gameId}/rounds/${store.roundNo}/vote`,
      { target_player_id: selectedTargetId.value },
      { headers: { "X-Player-Token": store.playerToken } }
    );
    ElMessage.success("投票成功");
    await store.fetchSnapshot(roomCode.value);
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail?.message || "投票失败");
  } finally {
    voting.value = false;
  }
}

async function submitGuess() {
  if (!canGuess.value) return;
  if (!guessText.value.trim()) {
    ElMessage.warning("请输入猜词内容");
    return;
  }
  guessing.value = true;
  try {
    const res = await http.post(
      `/api/games/${store.gameId}/rounds/${store.roundNo}/guess`,
      { guess_text: guessText.value.trim() },
      { headers: { "X-Player-Token": store.playerToken } }
    );
    ElMessage.success(res.data.hit ? "猜中，游戏结束" : "已提交猜词");
    guessText.value = "";
    await store.fetchSnapshot(roomCode.value);
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail?.message || "猜词失败");
  } finally {
    guessing.value = false;
  }
}

onMounted(async () => {
  store.connectWS(roomCode.value);
  await store.fetchSnapshot(roomCode.value);
});
</script>

<template>
  <div class="page" style="padding-bottom: 90px">
    <h1 class="page-title">玩家对局</h1>
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
      <p>阶段：{{ store.phase }}</p>
      <p>轮次：{{ store.roundNo }}</p>
      <p>我的身份：{{ roleText(me?.role) || "等待开局" }}</p>
      <p>我的身份词：{{ myWord || "等待开局" }}</p>
      <p v-if="(store as any).game?.winnerSide">胜方：{{ (store as any).game?.winnerSide }}</p>

      <div v-if="canVote" style="display: flex; gap: 8px; margin: 10px 0; align-items: center; flex-wrap: wrap">
        <el-select v-model="selectedTargetId" placeholder="选择投票目标" style="min-width: 220px">
          <el-option
            v-for="p in store.players"
            :key="p.id"
            :label="`#${p.seatNo} ${p.nickname}`"
            :value="p.id"
            :disabled="p.eliminated || p.id === store.playerId"
          />
        </el-select>
        <el-button type="primary" :loading="voting" @click="submitVote">投票</el-button>
      </div>
      <div v-else-if="(store as any).game?.myVoteSubmitted && (store.phase === 'ROUND_VOTING' || store.phase === 'ROUND_TIE_BREAK')">
        <el-tag type="success">本轮已投票</el-tag>
      </div>

      <div v-if="canGuess" style="display: flex; gap: 8px; margin: 10px 0; align-items: center; flex-wrap: wrap">
        <el-input v-model="guessText" placeholder="猜对面阵营词语" style="max-width: 300px" />
        <el-button type="warning" :loading="guessing" @click="submitGuess">提交猜词</el-button>
        <el-tag>
          已用 {{ (store as any).game?.myGuessUsed || 0 }} / {{ (store as any).game?.myGuessLimit || 0 }} 次
        </el-tag>
      </div>
      <div v-else-if="store.phase === 'ROUND_GUESSING' && ((store as any).game?.myGuessLimit || 0) > 0">
        <el-tag type="info">本轮猜词次数已用完</el-tag>
      </div>

      <el-table :data="store.players" size="small" :row-class-name="rowClassName">
        <el-table-column prop="seatNo" label="座位" width="70" />
        <el-table-column prop="nickname" label="昵称" />
        <el-table-column label="身份(可见范围内)">
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
