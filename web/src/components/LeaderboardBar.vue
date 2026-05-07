<script setup lang="ts">
import { computed } from "vue";
import { useRoomStore } from "../stores/room";
import { useDevice } from "../utils/device";

const store = useRoomStore();
const { isMobile } = useDevice();
const items = computed(() => store.leaderboard || []);
</script>

<template>
  <div class="bottom-board">
    <div class="board-items">
      <div
        v-for="(item, idx) in items"
        :key="item.playerId"
        class="board-item"
        :style="isMobile ? { minWidth: '120px', padding: '4px 6px' } : {}"
      >
        <div :style="isMobile ? { fontSize: '13px' } : {}">
          #{{ idx + 1 }} {{ item.nickname }}
        </div>
        <div :style="isMobile ? { fontSize: '12px', color: '#909399' } : {}">
          {{ item.totalScore }}分
        </div>
      </div>
    </div>
  </div>
</template>
