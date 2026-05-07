import { ref, onMounted } from "vue";

const isMobile = ref(false);

function checkMobile() {
  isMobile.value =
    /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(
      navigator.userAgent
    ) || window.innerWidth <= 768;
}

export function useDevice() {
  onMounted(() => {
    checkMobile();
    window.addEventListener("resize", checkMobile);
  });

  return { isMobile };
}
