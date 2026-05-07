<script setup lang="ts">
import { reactive } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";

import { http } from "../api/client";
import { useRoomStore } from "../stores/room";
import { useDevice } from "../utils/device";

const store = useRoomStore();
const router = useRouter();
const { isMobile } = useDevice();
const form = reactive({ roomCode: "", nickname: "" });

async function join() {
  if (!form.roomCode.trim() || !form.nickname.trim()) {
    ElMessage.warning("请输入房间号和昵称");
    return;
  }
  try {
    const res = await http.post(`/api/rooms/${form.roomCode}/join`, {
      nickname: form.nickname,
    });
    store.setPlayerToken(res.data.player_token, res.data.player_id);
    router.push(`/player/game/${form.roomCode}`);
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail?.message || "加入失败");
  }
}
</script>

<template>
  <!-- 移动端布局 -->
  <div v-if="isMobile" class="mobile-page">
    <div class="mobile-panel">
      <h1 class="mobile-title">谁是卧底</h1>
      <p style="text-align: center; color: #909399; margin-bottom: 16px">
        输入房间号和昵称加入游戏
      </p>
      <el-form label-position="top">
        <el-form-item label="房间号">
          <el-input
            v-model="form.roomCode"
            maxlength="6"
            placeholder="6位数字"
            size="large"
          />
        </el-form-item>
        <el-form-item label="昵称">
          <el-input
            v-model="form.nickname"
            maxlength="30"
            placeholder="输入昵称"
            size="large"
          />
        </el-form-item>
      </el-form>
      <el-button type="primary" size="large" style="width: 100%" @click="join"
        >加入游戏</el-button
      >
      <div style="text-align: center; margin-top: 12px">
        <el-link href="/host/create">主持人入口</el-link>
      </div>
    </div>

    <!-- 游戏规则 -->
    <div class="mobile-rules-card">
      <div class="mobile-rules-title">游戏规则</div>
      <div class="mobile-rules-content">
        <p><strong>角色分配：</strong></p>
        <p>• 平民：拿到相同词语，通过发言找出卧底</p>
        <p>• 卧底：拿到相似词语，隐藏身份</p>
        <p>• 白板：无固定词语，靠猜词获胜</p>
        <p style="margin-top: 8px"><strong>胜利条件：</strong></p>
        <p>• 平民：投票淘汰所有卧底</p>
        <p>• 卧底：卧底人数 ≥ 平民人数</p>
        <p>• 白板：猜中任意阵营词语</p>
        <p style="margin-top: 8px"><strong>游戏流程：</strong></p>
        <p>发言 → 投票 → 猜词 → 结算</p>
      </div>
    </div>
  </div>

  <!-- PC端布局 -->
  <div v-else class="page">
    <div class="panel" style="max-width: 520px; margin: 24px auto">
      <h1 class="page-title">玩家加入房间</h1>
      <el-form label-position="top">
        <el-form-item label="房间号">
          <el-input
            v-model="form.roomCode"
            maxlength="6"
            placeholder="6位数字"
          />
        </el-form-item>
        <el-form-item label="昵称">
          <el-input v-model="form.nickname" maxlength="30" placeholder="输入昵称" />
        </el-form-item>
      </el-form>
      <el-button type="primary" @click="join">加入</el-button>
      <el-link href="/host/create" style="margin-left: 12px"
        >主持人入口</el-link
      >
    </div>
  </div>
</template>
