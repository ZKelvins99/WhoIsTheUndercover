<script setup lang="ts">
import { reactive } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";

import { http } from "../api/client";
import { useRoomStore } from "../stores/room";

const store = useRoomStore();
const router = useRouter();
const form = reactive({ roomCode: "", nickname: "" });

async function join() {
  try {
    const res = await http.post(`/api/rooms/${form.roomCode}/join`, { nickname: form.nickname });
    store.setPlayerToken(res.data.player_token, res.data.player_id);
    router.push(`/player/game/${form.roomCode}`);
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail?.message || "加入失败");
  }
}
</script>

<template>
  <div class="page">
    <div class="panel" style="max-width: 520px; margin: 24px auto">
      <h1 class="page-title">玩家加入房间</h1>
      <el-form label-position="top">
        <el-form-item label="房间号">
          <el-input v-model="form.roomCode" maxlength="6" placeholder="6位数字" />
        </el-form-item>
        <el-form-item label="昵称">
          <el-input v-model="form.nickname" maxlength="30" placeholder="输入昵称" />
        </el-form-item>
      </el-form>
      <el-button type="primary" @click="join">加入</el-button>
      <el-link href="/host/create" style="margin-left: 12px">主持人入口</el-link>
    </div>
  </div>
</template>
