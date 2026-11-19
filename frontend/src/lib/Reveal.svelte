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

	Props: delay?=0 (мс), y?=14 (px підйому), class?:string, children
	Обгортка — звичайний <div> (display:block); для grid/flex дайте їй свій class.
-->
<script lang="ts">
	import type { Snippet } from 'svelte';
	import { isReduced } from './motion.ts';

	let {
		delay = 0,
		y = 14,
		class: klass = '',
		children
	}: { delay?: number; y?: number; class?: string; children: Snippet } = $props();

	let el = $state<HTMLDivElement>();
	let shown = $state(false);

	$effect(() => {
		if (!el) return;
		if (isReduced() || typeof IntersectionObserver === 'undefined') {
			shown = true;
			return;
		}
		const io = new IntersectionObserver(
			(entries) => {
				if (entries.some((e) => e.isIntersecting)) {
					shown = true;
					io.disconnect();
				}
			},
			{ rootMargin: '0px 0px -6% 0px', threshold: 0.05 }
		);
		io.observe(el);
		return () => io.disconnect();
	});
</script>

<div
	bind:this={el}
	class="reveal {klass}"
	class:in={shown}
	style:--rv-delay="{delay}ms"
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
				opacity 520ms cubic-bezier(0.22, 1, 0.36, 1) var(--rv-delay),
				transform 620ms cubic-bezier(0.22, 1, 0.36, 1) var(--rv-delay);
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
