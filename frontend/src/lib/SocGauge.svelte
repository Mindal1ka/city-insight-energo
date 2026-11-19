<script lang="ts">
	// Напівкругла шкала заряду акумулятора, 0–100 %. Дуга «наповнюється», коли шкала з’являється на екрані.
	// Стан передано кольором, словом («низький / середній / добрий») і числом — не лише кольором.
	import { num } from './format.ts';
	import { isReduced } from './motion.ts';
	import CountUp from './CountUp.svelte';

	let { pct, size = 180 }: { pct: number | null; size?: number } = $props();

	const R = 80;
	const C = Math.PI * R; // довжина півкола
	const v = $derived(pct === null ? 0 : Math.max(0, Math.min(100, pct)));
	const color = $derived(v < 20 ? '#c2410c' : v < 50 ? '#e08a00' : '#1a7f37');
	const word = $derived(pct === null ? 'немає даних' : v < 20 ? 'низький' : v < 50 ? 'середній' : 'добрий');

	let seen = $state(false);
	function onView(node: HTMLElement) {
		if (isReduced() || typeof IntersectionObserver === 'undefined') {
			seen = true;
			return;
		}
		const io = new IntersectionObserver(
			(es) => {
				if (es.some((e) => e.isIntersecting)) {
					seen = true;
					io.disconnect();
				}
			},
			{ threshold: 0.3 }
		);
		io.observe(node);
		return () => io.disconnect();
	}
	const shown = $derived(seen ? v : 0);
</script>

<div class="g" style="width: {size}px" {@attach onView}>
	<svg viewBox="0 0 200 150" role="img" aria-label="Заряд акумулятора {num(pct, 0)} %, {word}">
		<path d="M20 100 A80 80 0 0 1 180 100" fill="none" stroke="#e6ebf1" stroke-width="16" stroke-linecap="round" />
		<path
			class="arc"
			d="M20 100 A80 80 0 0 1 180 100"
			fill="none"
			stroke={color}
			stroke-width="16"
			stroke-linecap="round"
			stroke-dasharray="{(shown / 100) * C} {C}"
			opacity={shown > 0 ? 1 : 0}
		/>
		{#each [0, 25, 50, 75, 100] as t (t)}
			{@const a = Math.PI * (1 - t / 100)}
			<line
				x1={100 + Math.cos(a) * 64}
				y1={100 - Math.sin(a) * 64}
				x2={100 + Math.cos(a) * 58}
				y2={100 - Math.sin(a) * 58}
				stroke="#9aa6b4"
				stroke-width="2"
			/>
		{/each}
	</svg>
	<div class="val" aria-hidden="true">
		<span class="big-num">{#if seen}<CountUp value={pct} duration={1100} />{:else}0{/if}<span class="unit-s">%</span></span>
		<span class="word">заряд · {word}</span>
	</div>
</div>

<style>
	.g {
		position: relative;
		max-width: 100%;
	}
	svg {
		display: block;
		width: 100%;
		height: auto;
	}
	.arc {
		transition:
			stroke-dasharray 1.1s cubic-bezier(0.22, 1, 0.36, 1),
			stroke 0.4s;
	}
	.val {
		position: absolute;
		left: 0;
		right: 0;
		bottom: 0;
		text-align: center;
		display: flex;
		flex-direction: column;
		align-items: center;
	}
	.big-num {
		font-size: 1.9rem;
	}
	.word {
		font-size: 0.8rem;
		color: var(--muted);
		font-weight: 600;
	}
	@media (prefers-reduced-motion: reduce) {
		.arc {
			transition: none;
		}
	}
</style>
