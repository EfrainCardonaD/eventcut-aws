<script setup>
import LandingBackground from '@/components/illustrations/LandingBackground.vue'
</script>

<template>
  <main class="min-h-screen bg-slate-50 text-slate-900 selection:bg-tertiary-400/30 dark:bg-slate-950 dark:text-slate-100 relative">
    <LandingBackground />
    <div class="relative z-10 w-full">
      <router-view />
    </div>
  </main>
</template>
