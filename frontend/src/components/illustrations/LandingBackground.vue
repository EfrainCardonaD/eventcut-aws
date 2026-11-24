<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { TresCanvas } from '@tresjs/core'
import LandingBackgroundScene from './LandingBackgroundScene.vue'

const canvasRef = ref(null)

const isDark = ref(false)

const updateTheme = () => {
  if (typeof document === 'undefined') return
  isDark.value = document.documentElement.classList.contains('dark')
}

let mutationObserver = null

onMounted(() => {
  updateTheme()
  
  if (typeof document !== 'undefined') {
    mutationObserver = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        if (mutation.attributeName === 'class') {
          updateTheme()
        }
      })
    })
    
    mutationObserver.observe(document.documentElement, {
      attributes: true
    })
  }
})

onUnmounted(() => {
  if (mutationObserver) {
    mutationObserver.disconnect()
  }
})
</script>

<template>
  <div 
    class="fixed z-0 overflow-hidden pointer-events-none transition-colors duration-1000 opacity-30" 
    style="top: -20vh; left: -10vw; width: 120vw; height: 140vh; transform: translateZ(0); will-change: transform;"
    aria-hidden="true"
  >
    <TresCanvas :clearColor="isDark ? '#0f1418' : '#f8fafc'" antialias ref="canvasRef">
      <LandingBackgroundScene :is-dark="isDark" />
    </TresCanvas>
  </div>
</template>
