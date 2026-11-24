<script setup>
import { computed, ref, useAttrs } from 'vue'

defineOptions({
  inheritAttrs: false,
})

const props = defineProps({
  modelValue: {
    type: [String, Number],
    default: '',
  },
  type: {
    type: String,
    default: 'date',
    validator: (value) => ['date', 'time'].includes(value),
  },
  inputClass: {
    type: String,
    default: '',
  },
  iconClass: {
    type: String,
    default: '',
  },
  disabled: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['update:modelValue', 'change', 'blur', 'focus'])

const attrs = useAttrs()
const inputRef = ref(null)

const iconName = computed(() => (props.type === 'time' ? 'schedule' : 'calendar_month'))

const openPicker = () => {
  const inputEl = inputRef.value
  if (!inputEl || props.disabled) return

  inputEl.focus()

  if (typeof inputEl.showPicker === 'function') {
    try {
      inputEl.showPicker()
      return
    } catch {
      // Some browsers require strict user gestures for showPicker.
    }
  }

  inputEl.click()
}

const onInput = (event) => {
  emit('update:modelValue', event.target.value)
}
</script>

<template>
  <div class="relative">
    <input
      ref="inputRef"
      :value="modelValue"
      :type="type"
      :class="['native-picker-input w-full pr-11', inputClass]"
      :disabled="disabled"
      v-bind="attrs"
      @input="onInput"
      @change="emit('change', $event)"
      @blur="emit('blur', $event)"
      @focus="emit('focus', $event)"
      @click="openPicker"
    />

    <button
      type="button"
      class="absolute inset-y-0 right-0 z-[1] inline-flex w-11 items-center justify-center rounded-r-xl text-tertiary-600 transition-colors hover:text-tertiary-500 disabled:cursor-not-allowed disabled:text-slate-400 dark:text-tertiary-400 dark:hover:text-tertiary-300 dark:disabled:text-slate-600"
      :class="iconClass"
      :disabled="disabled"
      :aria-label="type === 'time' ? 'Seleccionar hora' : 'Seleccionar fecha'"
      @click.stop="openPicker"
    >
      <span class="material-symbols-outlined text-[20px]">{{ iconName }}</span>
    </button>
  </div>
</template>

<style scoped>
.native-picker-input::-webkit-calendar-picker-indicator {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  opacity: 0;
  cursor: pointer;
}

.native-picker-input::-webkit-clear-button {
  display: none;
}
</style>

