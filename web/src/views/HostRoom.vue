<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";

import { http } from "../api/client";
import { useRoomStore } from "../stores/room";
import LeaderboardBar from "../components/LeaderboardBar.vue";

const route = useRoute();
const router = useRouter();
const store = useRoomStore();
const roomCode = computed(() => String(route.params.roomCode || ""));
const locked = ref(false);
const startForm = ref({
  civilianCount: 8,
  undercoverCount: 2,
  blankCount: 0,
  civilianWord: "苹果",
  undercoverWord: "梨",
});

const ROLE_TEMPLATES: Record<number, { c: number; u: number; b: number }> = {
  10: { c: 7, u: 2, b: 1 },
  11: { c: 8, u: 2, b: 1 },
  12: { c: 8, u: 3, b: 1 },
  13: { c: 9, u: 3, b: 1 },
  14: { c: 9, u: 3, b: 2 },
  15: { c: 10, u: 3, b: 2 },
};

const playerCount = computed(() => store.players.length);

watch(playerCount, (n) => {
  const tpl = ROLE_TEMPLATES[n];
  if (tpl) {
    startForm.value.civilianCount = tpl.c;
    startForm.value.undercoverCount = tpl.u;
    startForm.value.blankCount = tpl.b;
  }
});

const roleTotal = computed(
  () =>
    startForm.value.civilianCount +
    startForm.value.undercoverCount +
    startForm.value.blankCount
);

async function refresh() {
  await store.fetchSnapshot(roomCode.value);
}

async function toggleLock() {
  await http.post(
    `/api/rooms/${roomCode.value}/lock`,
    { locked: !locked.value },
    { headers: { "X-Host-Secret": store.hostSecret } }
  );
  locked.value = !locked.value;
  await refresh();
}

async function kickPlayer(id: number) {
  await http.post(`/api/rooms/${roomCode.value}/kick/${id}`, null, {
    headers: { "X-Host-Secret": store.hostSecret },
  });
  await refresh();
}

async function startGame() {
  try {
    const alive = store.players.length;
    if (roleTotal.value > alive) {
      ElMessage.error("角色总人数不能超过在场人数");
      return;
    }
    if (!startForm.value.civilianWord || !startForm.value.undercoverWord) {
      ElMessage.error("请填写平民词和卧底词");
      return;
    }
    const res = await http.post(
      `/api/rooms/${roomCode.value}/games/start`,
      {
        civilian_count: startForm.value.civilianCount,
        undercover_count: startForm.value.undercoverCount,
        blank_count: startForm.value.blankCount,
        civilian_word: startForm.value.civilianWord,
        undercover_word: startForm.value.undercoverWord,
      },
      { headers: { "X-Host-Secret": store.hostSecret } }
    );
    store.gameId = res.data.gameId;
    router.push(`/host/game/${roomCode.value}`);
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail?.message || "开局失败");
  }
}

onMounted(async () => {
  store.connectWS(roomCode.value);
  await refresh();
  locked.value = false;
});
</script>

<template>
  <div class="page" style="padding-bottom: 90px">
    <h1 class="page-title">房间大厅 {{ roomCode }}</h1>
    <div class="panel">
      <div style="display: flex; gap: 8px; margin-bottom: 10px">
        <el-button @click="toggleLock">{{
          locked ? "解锁房间" : "锁定房间"
        }}</el-button>
        <el-button type="primary" @click="startGame">开始游戏</el-button>
      </div>

      <div
        style="
          display: grid;
          grid-template-columns: repeat(2, minmax(180px, 1fr));
          gap: 12px;
          margin-bottom: 16px;
        "
      >
        <el-form-item label="平民人数">
          <el-input-number
            v-model="startForm.civilianCount"
            :min="0"
            :step="1"
          />
        </el-form-item>
        <el-form-item label="卧底人数">
          <el-input-number
            v-model="startForm.undercoverCount"
            :min="0"
            :step="1"
          />
        </el-form-item>
        <el-form-item label="白板人数">
          <el-input-number
            v-model="startForm.blankCount"
            :min="0"
            :step="1"
          />
        </el-form-item>
        <el-form-item label="总角色人数 / 在场人数">
          <el-input
            :model-value="`${roleTotal} / ${store.players.length}`"
            disabled
          />
        </el-form-item>
        <el-form-item label="平民词">
          <el-input
            v-model="startForm.civilianWord"
            maxlength="100"
            placeholder="例如：苹果"
          />
        </el-form-item>
        <el-form-item label="卧底词">
          <el-input
            v-model="startForm.undercoverWord"
            maxlength="100"
            placeholder="例如：梨"
          />
        </el-form-item>
      </div>

      <el-table :data="store.players" stripe>
        <el-table-column prop="seatNo" label="座位" width="80" />
        <el-table-column prop="nickname" label="昵称" />
        <el-table-column prop="eliminated" label="状态">
          <template #default="s">{{
            s.row.eliminated ? "出局" : "存活"
          }}</template>
        </el-table-column>
        <el-table-column label="操作" width="90">
          <template #default="s">
            <el-button link type="danger" @click="kickPlayer(s.row.id)"
              >踢人</el-button
            >
          </template>
        </el-table-column>
      </el-table>
    </div>
    <LeaderboardBar />
  </div>
</template>
