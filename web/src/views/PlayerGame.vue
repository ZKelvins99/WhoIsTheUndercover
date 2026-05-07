<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { ElMessage } from "element-plus";

import LeaderboardBar from "../components/LeaderboardBar.vue";
import { useRoomStore } from "../stores/room";
import { http } from "../api/client";
import { useDevice } from "../utils/device";

const route = useRoute();
const store = useRoomStore();
const roomCode = computed(() => String(route.params.roomCode || ""));
const { isMobile } = useDevice();
const voting = ref(false);
const selectedTargetId = ref<number | null>(null);
const guessing = ref(false);
const guessText = ref("");
const showRules = ref(false);
const hideIdentity = ref(false);

const me = computed(
  () => store.players.find((p: any) => p.id === store.playerId) || null
);
const myWord = computed(() => (store as any).game?.myWord || "");

const myRole = computed(() => me.value?.role || null);

const roleDescription = computed(() => {
  const role = myRole.value;
  if (role === "CIVILIAN") {
    return {
      name: "平民",
      desc: "你的任务是通过发言找出卧底。每轮可以描述你的词语（不能直接说出），投票淘汰可疑的卧底。如果猜到卧底的词语，可以在猜词阶段猜测。",
      tips: "• 描述时要具体但不能太明显\n• 注意听其他玩家的描述\n• 寻找描述模糊或矛盾的人",
    };
  }
  if (role === "UNDERCOVER") {
    return {
      name: "卧底",
      desc: "你的任务是隐藏身份，存活到最后。你拿到的是相似词语，要模仿平民的描述方式。当卧底人数≥平民人数时，卧底阵营胜利。",
      tips: "• 观察平民的描述，模仿他们的思路\n• 不要描述得太具体或太模糊\n• 投票时要显得自然",
    };
  }
  if (role === "BLANK") {
    return {
      name: "白板",
      desc: "你没有固定词语，需要通过听其他玩家的描述来猜测词语。白板每轮有2次猜词机会，猜中任意阵营词语即可独立获胜。",
      tips: "• 仔细听所有人的描述\n• 推测平民词和卧底词\n• 猜词时要果断",
    };
  }
  return null;
});

const tiedPlayerIds = computed<number[]>(() => {
  const raw = (store as any).game?.tiedPlayerIds;
  if (!raw) return [];
  if (Array.isArray(raw)) return raw;
  try {
    return JSON.parse(raw);
  } catch {
    return [];
  }
});

const canVote = computed(
  () =>
    !!store.gameId &&
    (store.phase === "ROUND_VOTING" || store.phase === "ROUND_TIE_BREAK") &&
    !!me.value &&
    !me.value.eliminated &&
    !(store as any).game?.myVoteSubmitted
);

const voteTargets = computed(() => {
  if (store.phase === "ROUND_TIE_BREAK" && tiedPlayerIds.value.length > 0) {
    const tiedSet = new Set(tiedPlayerIds.value);
    return store.players.filter(
      (p: any) => tiedSet.has(p.id) && !p.eliminated
    );
  }
  return store.players.filter(
    (p: any) => !p.eliminated && p.id !== store.playerId
  );
});

const canGuess = computed(
  () =>
    !!store.gameId &&
    store.phase === "ROUND_GUESSING" &&
    !!me.value &&
    !me.value.eliminated &&
    ((store as any).game?.myGuessUsed || 0) <
      ((store as any).game?.myGuessLimit || 0)
);

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

function roleText(role?: string | null) {
  if (!role) return "";
  if (role === "CIVILIAN") return "平民";
  if (role === "UNDERCOVER") return "卧底";
  if (role === "BLANK") return "白板";
  return role;
}

function roleClass(role?: string | null) {
  if (role === "CIVILIAN") return "civilian";
  if (role === "UNDERCOVER") return "undercover";
  if (role === "BLANK") return "blank";
  return "";
}

function rowClassName({ row }: { row: any }) {
  if (row.id === store.currentSpeakerId) return "row-current-speaker";
  if (row.eliminated) return "row-eliminated";
  if (row.spoken) return "row-spoken";
  return "";
}

function playerItemClass(p: any) {
  if (p.id === store.currentSpeakerId) return "current-speaker";
  if (p.eliminated) return "eliminated";
  if (p.spoken) return "spoken";
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
    ElMessage.success(res.data.hit ? "猜中，游戏结束！" : "已提交猜词");
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
  <!-- 移动端布局 -->
  <div v-if="isMobile" class="mobile-page">
    <!-- 发言人弹窗 -->
    <el-dialog
      v-model="store.speakerDialogVisible"
      :show-close="false"
      :close-on-click-modal="true"
      :close-on-press-escape="false"
      width="90%"
      center
      @close="store.speakerDialogVisible = false"
    >
      <div style="text-align: center; padding: 20px 0">
        <div style="font-size: 14px; color: #909399; margin-bottom: 12px">
          当前发言人
        </div>
        <div style="font-size: 36px; font-weight: bold; color: #409eff">
          {{
            store.speakerNotice.replace("请 ", "").replace(" 发言", "")
          }}
        </div>
        <div style="font-size: 14px; color: #909399; margin-top: 12px">
          请开始发言
        </div>
      </div>
    </el-dialog>

    <!-- 房间信息 -->
    <div class="mobile-panel">
      <div class="mobile-info-row">
        <span class="mobile-info-label">房间</span>
        <span class="mobile-info-value">{{ roomCode }}</span>
      </div>
      <div class="mobile-info-row">
        <span class="mobile-info-label">阶段</span>
        <span class="mobile-info-value" style="color: #409eff; font-weight: bold">{{
          phaseText
        }}</span>
      </div>
      <div class="mobile-info-row">
        <span class="mobile-info-label">轮次</span>
        <span class="mobile-info-value">{{ store.roundNo }}</span>
      </div>
      <div v-if="(store as any).game?.winnerSide" class="mobile-info-row">
        <span class="mobile-info-label">胜方</span>
        <span class="mobile-info-value" style="color: #e6a23c">{{
          (store as any).game?.winnerSide
        }}</span>
      </div>
    </div>

    <!-- 角色信息卡片 -->
    <div v-if="myRole" class="mobile-role-card" :class="roleClass(myRole)">
      <div style="display: flex; justify-content: flex-end; margin-bottom: 8px">
        <el-button
          size="small"
          :type="hideIdentity ? 'warning' : 'info'"
          @click="hideIdentity = !hideIdentity"
          style="padding: 4px 8px"
        >
          {{ hideIdentity ? "显示身份" : "隐藏身份" }}
        </el-button>
      </div>
      <template v-if="!hideIdentity">
        <div class="mobile-role-name">{{ roleDescription?.name }}</div>
        <div class="mobile-role-word">{{ myWord }}</div>
        <div class="mobile-role-desc">{{ roleDescription?.desc }}</div>
      </template>
      <template v-else>
        <div style="font-size: 18px; padding: 20px 0; text-align: center">
          身份已隐藏，点击"显示身份"查看
        </div>
      </template>
    </div>

    <!-- 等待开局提示 -->
    <div v-else class="mobile-panel" style="text-align: center; color: #909399">
      等待主持人开始游戏...
    </div>

    <!-- 角色特点和提示 -->
    <div v-if="myRole" class="mobile-rules-card" @click="showRules = !showRules">
      <div class="mobile-rules-title" style="cursor: pointer">
        {{ showRules ? "收起" : "查看" }}角色攻略
        <span style="float: right">{{ showRules ? "▲" : "▼" }}</span>
      </div>
      <div v-if="showRules" class="mobile-rules-content" style="margin-top: 8px">
        <p style="white-space: pre-line">{{ roleDescription?.tips }}</p>
      </div>
    </div>

    <!-- 投票区域 -->
    <div v-if="canVote" class="mobile-panel mobile-vote-section">
      <div style="font-weight: bold; margin-bottom: 8px">选择投票目标</div>
      <div style="display: flex; flex-direction: column; gap: 8px">
        <el-button
          v-for="p in voteTargets"
          :key="p.id"
          :type="selectedTargetId === p.id ? 'primary' : 'default'"
          @click="selectedTargetId = p.id"
        >
          #{{ p.seatNo }} {{ p.nickname }}
        </el-button>
      </div>
      <el-button
        type="primary"
        size="large"
        style="width: 100%; margin-top: 12px"
        :loading="voting"
        :disabled="!selectedTargetId"
        @click="submitVote"
        >确认投票</el-button
      >
    </div>
    <div
      v-else-if="
        (store as any).game?.myVoteSubmitted &&
        (store.phase === 'ROUND_VOTING' || store.phase === 'ROUND_TIE_BREAK')
      "
      class="mobile-panel"
      style="text-align: center"
    >
      <el-tag type="success" size="large">本轮已投票</el-tag>
    </div>

    <!-- 猜词区域 -->
    <div v-if="canGuess" class="mobile-panel mobile-guess-section">
      <div style="font-weight: bold; margin-bottom: 8px">猜词</div>
      <el-input
        v-model="guessText"
        placeholder="猜对面阵营词语"
        size="large"
      />
      <div style="margin-top: 8px; color: #909399; font-size: 13px">
        已用 {{ (store as any).game?.myGuessUsed || 0 }} /
        {{ (store as any).game?.myGuessLimit || 0 }} 次
      </div>
      <el-button
        type="warning"
        size="large"
        style="width: 100%; margin-top: 8px"
        :loading="guessing"
        :disabled="!guessText.trim()"
        @click="submitGuess"
        >提交猜词</el-button
      >
    </div>
    <div
      v-else-if="
        store.phase === 'ROUND_GUESSING' &&
        ((store as any).game?.myGuessLimit || 0) > 0
      "
      class="mobile-panel"
      style="text-align: center"
    >
      <el-tag type="info" size="large">本轮猜词次数已用完</el-tag>
    </div>

    <!-- 玩家列表 -->
    <div class="mobile-panel">
      <div style="font-weight: bold; margin-bottom: 8px">玩家列表</div>
      <div class="mobile-player-list">
        <div
          v-for="p in store.players"
          :key="p.id"
          class="mobile-player-item"
          :class="playerItemClass(p)"
        >
          <div class="mobile-player-info">
            <div class="mobile-player-seat">{{ p.seatNo }}</div>
            <div class="mobile-player-name">{{ p.nickname }}</div>
          </div>
          <div style="display: flex; align-items: center; gap: 8px">
            <span v-if="p.role" style="font-size: 12px; color: #909399">{{
              roleText(p.role)
            }}</span>
            <span
              v-if="p.eliminated"
              class="mobile-player-status"
              style="background: #fef0f0; color: #f56c6c"
              >出局</span
            >
            <span
              v-else-if="p.spoken"
              class="mobile-player-status"
              style="background: #f0f9ff; color: #409eff"
              >已发言</span
            >
            <span
              v-else
              class="mobile-player-status"
              style="background: #f4f4f5; color: #909399"
              >未发言</span
            >
          </div>
        </div>
      </div>
    </div>

    <!-- 排行榜 -->
    <LeaderboardBar />
  </div>

  <!-- PC端布局 -->
  <div v-else class="page" style="padding-bottom: 90px">
    <h1 class="page-title">玩家对局</h1>

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
        <div style="font-size: 16px; color: #909399; margin-bottom: 12px">
          当前发言人
        </div>
        <div style="font-size: 32px; font-weight: bold; color: #409eff">
          {{
            store.speakerNotice.replace("请 ", "").replace(" 发言", "")
          }}
        </div>
        <div style="font-size: 14px; color: #909399; margin-top: 12px">
          请开始发言
        </div>
      </div>
    </el-dialog>

    <div class="panel">
      <p>房间：{{ roomCode }}</p>
      <p>阶段：<strong>{{ phaseText }}</strong></p>
      <p>轮次：{{ store.roundNo }}</p>

      <div v-if="myRole" style="margin: 12px 0">
        <el-button
          size="small"
          :type="hideIdentity ? 'warning' : 'info'"
          @click="hideIdentity = !hideIdentity"
        >
          {{ hideIdentity ? "显示身份" : "隐藏身份" }}
        </el-button>
      </div>

      <template v-if="!hideIdentity">
        <p>我的身份：{{ roleText(me?.role) || "等待开局" }}</p>
        <p>我的身份词：{{ myWord || "等待开局" }}</p>

        <!-- 角色特点 -->
        <div
          v-if="myRole"
          style="
            background: #f0f9ff;
            border: 1px solid #b3d8ff;
            border-radius: 8px;
            padding: 12px;
            margin: 12px 0;
          "
        >
          <div style="font-weight: bold; color: #409eff; margin-bottom: 4px">
            {{ roleDescription?.name }}特点
          </div>
          <div style="font-size: 14px; color: #606266; line-height: 1.6">
            {{ roleDescription?.desc }}
          </div>
        </div>
      </template>
      <template v-else>
        <p style="color: #909399">身份已隐藏，点击"显示身份"查看</p>
      </template>

      <p v-if="(store as any).game?.winnerSide">
        胜方：{{ (store as any).game?.winnerSide }}
      </p>

      <div v-if="canVote" style="display: flex; gap: 8px; margin: 10px 0; align-items: center; flex-wrap: wrap">
        <el-select
          v-model="selectedTargetId"
          placeholder="选择投票目标"
          style="min-width: 220px"
        >
          <el-option
            v-for="p in voteTargets"
            :key="p.id"
            :label="`#${p.seatNo} ${p.nickname}`"
            :value="p.id"
          />
        </el-select>
        <el-button type="primary" :loading="voting" @click="submitVote"
          >投票</el-button
        >
      </div>
      <div
        v-else-if="
          (store as any).game?.myVoteSubmitted &&
          (store.phase === 'ROUND_VOTING' || store.phase === 'ROUND_TIE_BREAK')
        "
      >
        <el-tag type="success">本轮已投票</el-tag>
      </div>

      <div v-if="canGuess" style="display: flex; gap: 8px; margin: 10px 0; align-items: center; flex-wrap: wrap">
        <el-input
          v-model="guessText"
          placeholder="猜对面阵营词语"
          style="max-width: 300px"
        />
        <el-button type="warning" :loading="guessing" @click="submitGuess"
          >提交猜词</el-button
        >
        <el-tag>
          已用 {{ (store as any).game?.myGuessUsed || 0 }} /
          {{ (store as any).game?.myGuessLimit || 0 }} 次
        </el-tag>
      </div>
      <div
        v-else-if="
          store.phase === 'ROUND_GUESSING' &&
          ((store as any).game?.myGuessLimit || 0) > 0
        "
      >
        <el-tag type="info">本轮猜词次数已用完</el-tag>
      </div>

      <el-table
        :data="store.players"
        size="small"
        :row-class-name="rowClassName"
      >
        <el-table-column prop="seatNo" label="座位" width="70" />
        <el-table-column prop="nickname" label="昵称" />
        <el-table-column label="身份(可见范围内)">
          <template #default="s">{{ roleText(s.row.role) }}</template>
        </el-table-column>
        <el-table-column prop="spoken" label="发言">
          <template #default="s">{{
            s.row.spoken ? "已发言" : "未发言"
          }}</template>
        </el-table-column>
        <el-table-column prop="eliminated" label="状态">
          <template #default="s">{{
            s.row.eliminated ? "出局" : "存活"
          }}</template>
        </el-table-column>
      </el-table>
    </div>
    <LeaderboardBar />
  </div>
</template>
