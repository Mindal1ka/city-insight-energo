<!--
	Текст/число, у якому при зміні «прокручуються» лише змінені символи (як цифри K у KBadge).
	Ніякого набігання від нуля: перший показ — миттєво; далі змінений символ заходить
	знизу (значення зросло) або згори (зменшилося), 160 мс, лише opacity + transform.

	  <Roll text={num(v)} value={v} />
-->
<script lang="ts">
	import type { TransitionConfig } from 'svelte/transition';
	import { isReduced, EASE, DUR } from './motion.ts';

	let { text, value = null }: { text: string; value?: number | null } = $props();

	const chars = $derived([...text]);
	let prev: number | null = null;
	let dir = 1;
	$effect.pre(() => {
		const v = value;
		if (v != null && prev != null && v !== prev) dir = v > prev ? 1 : -1;
		prev = v;
	});
	function roll(_n: Element): TransitionConfig {
		if (isReduced()) return { duration: 0 };
		const d = dir;
		return {
			duration: DUR.fast + 20,
			easing: EASE.out,
			css: (t, u) => `opacity:${t.toFixed(3)};transform:translateY(${(u * 0.6 * d).toFixed(3)}em)`
		};
	}
</script>

<span class="roll" aria-label={text}><span aria-hidden="true">{#each chars as c, i (i + ':' + c)}<span class="d" in:roll>{c}</span>{/each}</span></span>

<style>
	.roll {
		white-space: pre;
	}
	.d {
		display: inline-block;
		white-space: pre;
	}
</style>
