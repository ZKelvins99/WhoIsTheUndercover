<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";

import { http } from "../api/client";
import { useRoomStore } from "../stores/room";

const store = useRoomStore();
const router = useRouter();
const loading = ref(false);

async function createRoom() {
  loading.value = true;
  try {
    const res = await http.post("/api/host/rooms");
    store.setHostSecret(res.data.host_secret);
    router.push(`/host/room/${res.data.room_code}`);
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail?.message || "创建房间失败");
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="page">
    <div class="panel" style="max-width: 520px; margin: 40px auto">
      <h1 class="page-title">主持人创建房间</h1>
      <el-button type="primary" :loading="loading" @click="createRoom">创建 6 位房间号</el-button>
      <div style="margin-top: 12px">
        <el-link href="/player/join">去玩家加入页</el-link>
      </div>
    </div>
  </div>
</template>
