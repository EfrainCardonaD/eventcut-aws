<script setup>
import { shallowRef, ref, onMounted } from 'vue'
import { useLoop } from '@tresjs/core'
import * as THREE from 'three'

const props = defineProps({
  isDark: {
    type: Boolean,
    default: false
  }
})

// === COLORES ORIGINALES EXTRAIDOS DE LA REFERENCIA SVG ===
const c = {
  primary600: '#4c4be9',
  primary500: '#5e64ff',
  primary400: '#8090ff',
  secondary400: '#00b8b9',
  secondary300: '#44d6d6',
  tertiary500: '#ec0050',
  tertiary400: '#ff5c75',
  darkSurface: '#0b0f13',
  lightSurface: '#ffffff'
}

// === TEXTURAS ===
const createGlowTexture = () => {
    if (typeof document === 'undefined') return null
    const canvas = document.createElement('canvas')
    canvas.width = 256
    canvas.height = 256
    const ctx = canvas.getContext('2d')
    const gradient = ctx.createRadialGradient(128, 128, 0, 128, 128, 128)
    gradient.addColorStop(0, 'rgba(255, 255, 255, 1)')
    gradient.addColorStop(0.4, 'rgba(255, 255, 255, 0.5)')
    gradient.addColorStop(1, 'rgba(255, 255, 255, 0)')
    ctx.fillStyle = gradient
    ctx.fillRect(0, 0, 256, 256)
    return new THREE.CanvasTexture(canvas)
}

const createLinearGradientTexture = (colorA, colorB, colorC) => {
    if (typeof document === 'undefined') return null
    const canvas = document.createElement('canvas')
    canvas.width = 512
    canvas.height = 8
    const ctx = canvas.getContext('2d')
    const gradient = ctx.createLinearGradient(0, 0, 512, 0)
    gradient.addColorStop(0, colorA)
    gradient.addColorStop(0.5, colorB)
    gradient.addColorStop(1, colorC)
    ctx.fillStyle = gradient
    ctx.fillRect(0, 0, 512, 8)
    return new THREE.CanvasTexture(canvas)
}

const glowTexture = ref(createGlowTexture())
const waveGrad1 = ref(null)
const waveGrad2 = ref(null)
const waveGrad3 = ref(null)

onMounted(() => {
  waveGrad1.value = createLinearGradientTexture(c.tertiary400, c.tertiary500, c.primary600)
  waveGrad2.value = createLinearGradientTexture(c.secondary400, c.tertiary400, c.primary500)
  waveGrad3.value = createLinearGradientTexture(c.primary500, c.tertiary500, c.secondary400)
})

// === REFERENCIAS DE GEOMETRÍAS Y MALLAS ===
const glowCircle1 = shallowRef(null)
const glowCircle2 = shallowRef(null)

// Configuración de ondas enviadas al Vertex Shader (GPU)
const waveUniforms = {
  uTime: { value: 0 }
}

const customizeWaveMaterial = (config) => {
  return (shader) => {
    shader.uniforms.uTime = waveUniforms.uTime
    shader.uniforms.uSpeed = { value: config.speed }
    shader.uniforms.uAmp = { value: config.amp }
    shader.uniforms.uFreq = { value: config.freq }
    shader.uniforms.uPhase = { value: config.phase }
    
    shader.vertexShader = shader.vertexShader.replace(
      '#include <common>',
      `
      #include <common>
      uniform float uTime;
      uniform float uSpeed;
      uniform float uAmp;
      uniform float uFreq;
      uniform float uPhase;
      `
    )
    
    shader.vertexShader = shader.vertexShader.replace(
      '#include <begin_vertex>',
      `
      vec3 transformed = vec3( position );
      float newY = sin(transformed.x * uFreq + uTime * uSpeed + uPhase) * uAmp;
      transformed.y += newY;
      `
    )
  }
}

// Inyectores específicos para permitir caching separado en WebGL, ya que ocupan uniformes distintos.
const wave1Compile = customizeWaveMaterial({ amp: 2.2, freq: 0.1, speed: 0.4, phase: 0 })
const wave2Compile = customizeWaveMaterial({ amp: 1.8, freq: 0.12, speed: 0.25, phase: 10 })
const wave3Compile = customizeWaveMaterial({ amp: 1.5, freq: 0.15, speed: 0.35, phase: 25 })


// === InstancedMesh para las partículas (1 draw call = Rendimiento x30) ===
const particleCount = 30
const particlesInstancedMesh = shallowRef(null)
const dummy = new THREE.Object3D()
const colorPrimary = new THREE.Color(c.primary500)
const colorSecondary = new THREE.Color(c.secondary400)

const particlesData = Array.from({ length: particleCount }).map(() => ({
  x: (Math.random() - 0.5) * 40,
  y: (Math.random() - 0.5) * 25,
  z: (Math.random() - 0.5) * 5 - 2,
  speedY: Math.random() * 0.015 + 0.005,
  speedX: (Math.random() - 0.5) * 0.01,
  scale: Math.random() * 0.3 + 0.1,
  isPrimary: Math.random() > 0.5
}))

onMounted(() => {
  if (particlesInstancedMesh.value) {
    // Inicializar matrices y colores
    particlesData.forEach((p, i) => {
      dummy.position.set(p.x, p.y, p.z)
      dummy.rotation.z = Math.random() * Math.PI
      dummy.scale.set(p.scale, p.scale, 1)
      dummy.updateMatrix()
      particlesInstancedMesh.value.setMatrixAt(i, dummy.matrix)
      
      const color = p.isPrimary ? colorPrimary : colorSecondary
      particlesInstancedMesh.value.setColorAt(i, color)
    })
    particlesInstancedMesh.value.instanceMatrix.needsUpdate = true
    if (particlesInstancedMesh.value.instanceColor) {
      particlesInstancedMesh.value.instanceColor.needsUpdate = true
    }
  }
})

const { onBeforeRender } = useLoop()

onBeforeRender(({ elapsed }) => {
  // Solo se actualiza el tiempo base. Las matemáticas pesadas ocurren en la Tarjeta Gráfica.
  waveUniforms.uTime.value = elapsed

  if (glowCircle1.value) {
    glowCircle1.value.position.x = 4 + Math.cos(elapsed * 0.3) * 1.5
    glowCircle1.value.position.y = 2 + Math.sin(elapsed * 0.2) * 2
  }
  if (glowCircle2.value) {
    glowCircle2.value.position.x = -5 + Math.cos(elapsed * 0.2 + 5) * 2
    glowCircle2.value.position.y = -3 + Math.sin(elapsed * 0.4 + 2) * 1.5
  }

  // Update particles matrix in memory vs actual DOM nodes saves intense rendering
  if (particlesInstancedMesh.value) {
    particlesData.forEach((p, i) => {
      p.y += p.speedY
      p.x += p.speedX
      if (p.y > 15) p.y = -15
      if (p.x > 25) p.x = -25
      else if (p.x < -25) p.x = 25

      dummy.position.set(p.x, p.y, p.z)
      dummy.rotation.z = elapsed * 0.5
      dummy.scale.set(p.scale, p.scale, 1)
      dummy.updateMatrix()
      particlesInstancedMesh.value.setMatrixAt(i, dummy.matrix)
    })
    particlesInstancedMesh.value.instanceMatrix.needsUpdate = true
  }
})
</script>

<template>
  <TresPerspectiveCamera :position="[0, 0, 10]" :fov="45" :near="0.1" :far="1000" />

  <TresAmbientLight color="#ffffff" :intensity="1" />

  <!-- Ambient Glow Blobs -->
  <TresMesh ref="glowCircle1" :position="[4, 2, -5]">
    <TresPlaneGeometry :args="[30, 30]" />
    <TresMeshBasicMaterial
      :color="c.primary400"
      :map="glowTexture"
      :transparent="true"
      :opacity="isDark ? 0.3 : 0.6"
      :depthWrite="false"
    />
  </TresMesh>

  <TresMesh ref="glowCircle2" :position="[-5, -3, -4]">
    <TresPlaneGeometry :args="[36, 36]" />
    <TresMeshBasicMaterial
      :color="c.secondary300"
      :map="glowTexture"
      :transparent="true"
      :opacity="isDark ? 0.2 : 0.5"
      :depthWrite="false"
    />
  </TresMesh>

  <!-- Central Flare -->
  <TresMesh :position="[-2, -3, -2]" :scale="[15, 15, 1]">
    <TresPlaneGeometry :args="[1, 1]" />
    <TresMeshBasicMaterial
      :color="c.tertiary400"
      :map="glowTexture"
      :transparent="true"
      :opacity="isDark ? 0.15 : 0.4"
      :depthWrite="false"
    />
  </TresMesh>

  <!-- Wave Patterns: Trasladadas 100% a Shaders de GPU (onBeforeCompile) -->
  <TresMesh :position="[2, 0, -2]" :scale="[1, 0.4, 1]" :rotation="[0, 0, -0.25]">
    <TresPlaneGeometry :args="[60, 2, 80, 1]" />
    <TresMeshBasicMaterial
      :map="waveGrad1"
      :transparent="true"
      :opacity="isDark ? 0.4 : 0.8"
      :depthWrite="false"
      :side="2"
      :customProgramCacheKey="() => 'wave1'"
      :onBeforeCompile="wave1Compile"
    />
  </TresMesh>

  <TresMesh :position="[0, -1, -3]" :scale="[1, 0.3, 1]" :rotation="[0, 0, -0.4]">
    <TresPlaneGeometry :args="[60, 2, 80, 1]" />
    <TresMeshBasicMaterial
      :map="waveGrad2"
      :transparent="true"
      :opacity="isDark ? 0.5 : 0.9"
      :depthWrite="false"
      :side="2"
      :customProgramCacheKey="() => 'wave2'"
      :onBeforeCompile="wave2Compile"
    />
  </TresMesh>

  <TresMesh :position="[-2, -2, -1]" :scale="[1, 0.25, 1]" :rotation="[0, 0, 0.15]">
    <TresPlaneGeometry :args="[60, 2, 80, 1]" />
    <TresMeshBasicMaterial
      :map="waveGrad3"
      :transparent="true"
      :opacity="isDark ? 0.6 : 1"
      :depthWrite="false"
      :side="2"
      :customProgramCacheKey="() => 'wave3'"
      :onBeforeCompile="wave3Compile"
    />
  </TresMesh>

  <!-- Partículas Agrupadas en una InstancedMesh = 1 sola llamada de dibujado (1 Draw Call)-->
  <TresInstancedMesh ref="particlesInstancedMesh" :args="[null, null, particleCount]">
    <TresPlaneGeometry :args="[1, 1]" />
    <TresMeshBasicMaterial
      color="#ffffff"
      :map="glowTexture"
      :transparent="true" 
      :opacity="0.6"
      :depthWrite="false"
    />
  </TresInstancedMesh>

</template>
