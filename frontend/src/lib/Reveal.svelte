<!--
	Плавна поява блоку, коли він прокручується у видиму область (IntersectionObserver).
	Спрацьовує один раз. За prefers-reduced-motion і при друці — показується одразу.

	ВИКОРИСТАННЯ
	  import Reveal from '#lib/Reveal.svelte';
	  <Reveal>…будь-який вміст…</Reveal>
	  {#each cards as c, i (c.id)}
	    <Reveal delay={i * 60}><StatCard … /></Reveal>      // «драбинка» в сітці
	  {/each}
	  <Reveal y={24} class="my-grid-cell">…</Reveal>

	Props: delay?=0 (мс, діється на 2, ≤160), y?=6 (px підйому); у видимій області анімується лише в першій хвилі появи маршруту (motion.ts → inFirstWave), нижче екрана — завжди при прокручуванні; class?:string, children
	Обгортка — звичайний <div> (display:block); для grid/flex дайте їй свій class.
-->
<script lang="ts">
	import type { Snippet } from 'svelte';
	import { isReduced, inFirstWave, whenVisible } from './motion.ts';

	let {
		delay = 0,
		y = 6,
		class: klass = '',
		children
	}: { delay?: number; y?: number; class?: string; children: Snippet } = $props();

	let el = $state<HTMLDivElement>();
	let shown = $state(false);
	let instant = $state(false);

	$effect(() => {
		if (!el) return;
		if (isReduced() || typeof IntersectionObserver === 'undefined') {
			instant = true;
			shown = true;
			return;
		}
		const wave = inFirstWave();
		const r = el.getBoundingClientRect();
		const vh = window.innerHeight || document.documentElement.clientHeight;
		if (r.top < vh * 0.96) {
			// У видимій області (або вище чи прихований): рух лише в першій хвилі появи маршруту;
			// фільтри, повторні рендери — без руху
			if (!wave || r.bottom <= 0) instant = true;
			shown = true;
			return;
		}
		// Нижче екрана — з'являється, коли до нього прокрутять (спільний IntersectionObserver)
		return whenVisible(el, () => (shown = true));
	});
</script>

<div
	bind:this={el}
	class="reveal {klass}"
	class:in={shown}
	class:instant
	style:--rv-delay="{Math.min(Math.round(delay / 2), 160)}ms"
	style:--rv-y="{y}px"
>
	{@render children()}
</div>

<style>
	@media (prefers-reduced-motion: no-preference) {
		.reveal {
			opacity: 0;
			transform: translateY(var(--rv-y));
			transition:
				opacity var(--dur-base) var(--ease-out) var(--rv-delay),
				transform var(--dur-base) var(--ease-out) var(--rv-delay);
		}
		.reveal.instant {
			transition: none;
		}
		.reveal.in {
			opacity: 1;
			transform: none;
		}
	}
	@media print {
		.reveal {
			opacity: 1 !important;
			transform: none !important;
		}
	}
</style>
