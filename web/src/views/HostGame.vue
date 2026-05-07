<script setup lang="ts">
import { computed, onMounted, ref, reactive } from "vue";
import { useRoute } from "vue-router";
import { ElMessage } from "element-plus";

import { http } from "../api/client";
import LeaderboardBar from "../components/LeaderboardBar.vue";
import { useRoomStore } from "../stores/room";

const route = useRoute();
const store = useRoomStore();
const roomCode = computed(() => String(route.params.roomCode || ""));

// 新开一局表单
const newGameForm = reactive({
  civilianWord: "",
  undercoverWord: "",
  keepScores: true,
});
const showNewGameForm = ref(false);

// 加减分
const adjustAmounts = reactive<Record<number, number>>({});

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
    showNewGameForm.value = true;
    await store.fetchSnapshot(roomCode.value);
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail?.message || "结束失败");
  }
}

async function startNewGame() {
  if (!store.gameId) return;
  if (!newGameForm.civilianWord.trim() || !newGameForm.undercoverWord.trim()) {
    ElMessage.warning("请输入平民词和卧底词");
    return;
  }
  try {
    const res = await http.post(
      `/api/games/${store.gameId}/restart`,
      {
        civilian_word: newGameForm.civilianWord.trim(),
        undercover_word: newGameForm.undercoverWord.trim(),
        keep_scores: newGameForm.keepScores,
      },
      { headers: { "X-Host-Secret": store.hostSecret } }
    );
    store.gameId = res.data.gameId;
    showNewGameForm.value = false;
    newGameForm.civilianWord = "";
    newGameForm.undercoverWord = "";
    await store.fetchSnapshot(roomCode.value);
    ElMessage.success("新一局已开始");
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail?.message || "开局失败");
  }
}

async function adjustScore(playerId: number) {
  const amount = adjustAmounts[playerId];
  if (!amount || amount === 0) return;
  try {
    await http.post(
      `/api/rooms/${roomCode.value}/adjust-score`,
      { player_id: playerId, amount },
      { headers: { "X-Host-Secret": store.hostSecret } }
    );
    ElMessage.success(`已调整 ${nicknameOf(playerId)} 的分数 ${amount > 0 ? "+" : ""}${amount}`);
    adjustAmounts[playerId] = 0;
    await store.fetchSnapshot(roomCode.value);
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail?.message || "调整失败");
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

    <!-- 发言人弹窗 -->
    <el-dialog
      v-model="store.speakerDialogVisible"
      :show-close="false"
      :close-on-click-modal="true"
      :close-on-press-escape="false"
      width="360px"
      center
      @close="store.speakerDialogVisible = false"
    >
      <div style="text-align: center; padding: 20px 0">
        <div style="font-size: 16px; color: #909399; margin-bottom: 12px">当前发言人</div>
        <div style="font-size: 32px; font-weight: bold; color: #409eff">
          {{ store.speakerNotice.replace("请 ", "").replace(" 发言", "") }}
        </div>
        <div style="font-size: 14px; color: #909399; margin-top: 12px">请开始发言</div>
      </div>
    </el-dialog>

    <div class="panel">
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
      </div>

      <p v-if="(store as any).game?.winnerSide">
        胜方：{{ (store as any).game?.winnerSide }}
      </p>

      <!-- 新开一局表单 -->
      <div v-if="showNewGameForm || store.phase === 'GAME_FINISHED'" class="panel" style="margin-top: 16px; background: #f0f9ff">
        <h3 style="margin-bottom: 12px">新开一局</h3>
        <el-form label-width="80px">
          <el-form-item label="平民词">
            <el-input v-model="newGameForm.civilianWord" placeholder="请输入平民词" />
          </el-form-item>
          <el-form-item label="卧底词">
            <el-input v-model="newGameForm.undercoverWord" placeholder="请输入卧底词" />
          </el-form-item>
          <el-form-item label="分数处理">
            <el-radio-group v-model="newGameForm.keepScores">
              <el-radio :value="true">保留上局分数</el-radio>
              <el-radio :value="false">清零分数</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item>
            <el-button type="success" @click="startNewGame">开始新一局</el-button>
          </el-form-item>
        </el-form>
      </div>

      <!-- 手动加减分 -->
      <div v-if="store.players.length > 0" class="panel" style="margin-top: 16px; background: #fdf6ec">
        <h3 style="margin-bottom: 12px">手动加减分</h3>
        <el-table :data="store.players" size="small">
          <el-table-column prop="seatNo" label="座位" width="60" />
          <el-table-column prop="nickname" label="昵称" />
          <el-table-column label="当前分数" width="100">
            <template #default="s">
              {{ store.leaderboard.find((b: any) => b.playerId === s.row.id)?.totalScore || 0 }}
            </template>
          </el-table-column>
          <el-table-column label="调整分数" width="200">
            <template #default="s">
              <div style="display: flex; gap: 4px; align-items: center">
                <el-input-number
                  v-model="adjustAmounts[s.row.id]"
                  :min="-100"
                  :max="100"
                  size="small"
                  style="width: 100px"
                />
                <el-button
                  type="primary"
                  size="small"
                  @click="adjustScore(s.row.id)"
                  :disabled="!adjustAmounts[s.row.id]"
                >确认</el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <el-table :data="store.players" stripe :row-class-name="rowClassName" style="margin-top: 16px">
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
