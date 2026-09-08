<template><span class="brand-mark" aria-hidden="true"><img class="blue" :src="blue" alt="" /><img class="green" :src="green" alt="" /><img class="yellow" :src="yellow" alt="" /><i /><b>PM</b></span></template>
<script setup lang="ts">
import blue from '@/assets/figma/logo-blue.svg'
import green from '@/assets/figma/logo-green.svg'
import yellow from '@/assets/figma/logo-yellow.svg'
</script>
<style scoped>
.brand-mark { display:inline-block; position:relative; width:44px; height:44px; border-radius:14px; background:var(--pm-text); flex-shrink:0; }
img { position:absolute; width:20px; height:20px; } .blue { top:7px;left:7px; } .green { top:19px;left:19px; } .yellow { top:7px;left:30px;width:10px;height:10px; }
i { position:absolute; top:15px;left:17px;width:16px;height:2px;background:white; } b { position:absolute;top:16px;left:9px;width:28px;text-align:center;font-size:10px;line-height:14px;color:white; }
</style>
