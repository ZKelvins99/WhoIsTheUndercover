<script setup lang="ts">
import { computed } from "vue";
import { useRoomStore } from "../stores/room";

const store = useRoomStore();
const items = computed(() => store.leaderboard || []);
</script>

<template>
  <div class="bottom-board">
    <div class="board-items">
      <div v-for="(item, idx) in items" :key="item.playerId" class="board-item">
        <div>#{{ idx + 1 }} {{ item.nickname }}</div>
        <div>总分 {{ item.totalScore }}</div>
      </div>
    </div>
  </div>
</template>
