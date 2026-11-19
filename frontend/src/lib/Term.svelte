<script lang="ts">
	// Термін із поясненням простою мовою: пунктирне підкреслення + підказка.
	// Відкривається наведенням миші, фокусом з клавіатури й дотиком (тап), закривається Esc.
	// Використання: <Term key="автономність" /> або <Term key="СЕС">сонячна станція</Term>.
	// Не вкладайте в <a> чи <button>: сам термін — кнопка.
	import type { Snippet } from 'svelte';
	import { lookup } from './glossary.ts';

	let {
		key,
		children,
		plain = false
	}: {
		/** Ключ зі словника glossary.ts (або синонім) */
		key: string;
		/** Текст у рядку; за замовчуванням — сам ключ */
		children?: Snippet;
		/** Без маленького значка «?» */
		plain?: boolean;
	} = $props();

	const entry = $derived(lookup(key));
	const uid = 'term-' + Math.random().toString(36).slice(2, 9);

	let hover = $state(false);
	let focus = $state(false);
	let pinned = $state(false);
	let suppressed = $state(false);
	const open = $derived(!!entry && !suppressed && (hover || focus || pinned));

	let btn = $state<HTMLButtonElement>();
	let tip = $state<HTMLSpanElement>();
	let pos = $state({ left: 0, top: 0, above: false, arrow: 16 });

	let enterTimer: ReturnType<typeof setTimeout> | undefined;
	let leaveTimer: ReturnType<typeof setTimeout> | undefined;

	function pointerEnter(e: PointerEvent) {
		if (e.pointerType !== 'mouse') return; // на дотик реагує click
		clearTimeout(leaveTimer);
		enterTimer = setTimeout(() => (hover = true), 120);
	}
	function pointerLeave(e: PointerEvent) {
		if (e.pointerType !== 'mouse') return;
		clearTimeout(enterTimer);
		leaveTimer = setTimeout(() => {
			hover = false;
			suppressed = false;
		}, 180);
	}
	function click() {
		if (open) {
			if (pinned) {
				pinned = false;
				suppressed = true;
			} else pinned = true;
		} else {
			pinned = true;
			suppressed = false;
		}
	}
	function keydown(e: KeyboardEvent) {
		if (e.key === 'Escape' && open) {
			e.stopPropagation();
			pinned = false;
			suppressed = true;
		}
	}
	function blur() {
		focus = false;
		pinned = false;
		suppressed = false;
	}

	// Підказка «живе» в <body>, щоб її не обрізали таблиці з прокруткою й анімовані блоки
	function portal(node: HTMLElement) {
		document.body.appendChild(node);
		return () => node.remove();
	}

	function place() {
		if (!btn || !tip) return;
		const r = btn.getBoundingClientRect();
		const w = tip.offsetWidth;
		const h = tip.offsetHeight;
		const vw = document.documentElement.clientWidth;
		const vh = window.innerHeight;
		const gap = 10;
		let left = r.left + r.width / 2 - w / 2;
		left = Math.max(8, Math.min(left, vw - w - 8));
		const above = r.bottom + gap + h > vh - 8 && r.top - gap - h > 8;
		const top = above ? r.top - gap - h : r.bottom + gap;
		const arrow = Math.max(14, Math.min(r.left + r.width / 2 - left, w - 14));
		pos = { left, top, above, arrow };
	}

	$effect(() => {
		if (!open) return;
		place();
		const onMove = () => place();
		// Тап поза терміном закриває закріплену підказку
		const onDown = (e: PointerEvent) => {
			const t = e.target as Node;
			if (btn?.contains(t) || tip?.contains(t)) return;
			pinned = false;
			hover = false;
		};
		window.addEventListener('scroll', onMove, { capture: true, passive: true });
		window.addEventListener('resize', onMove);
		document.addEventListener('pointerdown', onDown);
		return () => {
			window.removeEventListener('scroll', onMove, { capture: true });
			window.removeEventListener('resize', onMove);
			document.removeEventListener('pointerdown', onDown);
		};
	});
</script>

{#if entry}<button
		bind:this={btn}
		type="button"
		class="term"
		aria-describedby={uid}
		onpointerenter={pointerEnter}
		onpointerleave={pointerLeave}
		onfocus={() => (focus = true)}
		onblur={blur}
		onclick={click}
		onkeydown={keydown}
		>{#if children}{@render children()}{:else}{key}{/if}{#if !plain}<span class="q" aria-hidden="true">?</span>{/if}</button
	><span
		bind:this={tip}
		{@attach portal}
		id={uid}
		role="tooltip"
		class="term-tip"
		class:open
		class:above={pos.above}
		style="left:{pos.left}px; top:{pos.top}px; --arrow:{pos.arrow}px"
		onpointerenter={pointerEnter}
		onpointerleave={pointerLeave}
		><span class="t">{entry.term}</span><span class="d">{entry.text}</span
		>{#if entry.example}<span class="e"><b>Наприклад:</b> {entry.example}</span>{/if}</span
	>{:else}{#if children}{@render children()}{:else}{key}{/if}{/if}

<style>
	.term {
		display: inline;
		padding: 0;
		margin: 0;
		border: 0;
		background: none;
		font: inherit;
		color: inherit;
		text-align: inherit;
		letter-spacing: inherit;
		text-transform: inherit;
		cursor: help;
		text-decoration: underline dotted;
		text-decoration-color: color-mix(in srgb, currentColor 55%, transparent);
		text-decoration-thickness: 1.5px;
		text-underline-offset: 0.2em;
		border-radius: 3px;
	}
	.term:hover {
		text-decoration-color: currentColor;
	}
	.q {
		display: inline-grid;
		place-items: center;
		width: 1.05em;
		height: 1.05em;
		margin-left: 0.2em;
		border-radius: 50%;
		background: color-mix(in srgb, currentColor 14%, transparent);
		font-size: 0.68em;
		font-weight: 700;
		line-height: 1;
		vertical-align: 0.35em;
		text-decoration: none;
	}
	.term-tip {
		position: fixed;
		z-index: 1000;
		display: none;
		flex-direction: column;
		gap: 0.3rem;
		width: max-content;
		max-width: min(23rem, calc(100vw - 16px));
		padding: 0.75rem 0.9rem;
		border-radius: 14px;
		background: #10243d;
		border: 1px solid rgba(255, 255, 255, 0.08);
		color: #f3f6fa;
		box-shadow: 0 12px 32px -8px rgba(10, 20, 35, 0.45);
		font-family: var(--font);
		font-size: 0.9375rem;
		font-weight: 400;
		line-height: 1.45;
		letter-spacing: 0;
		text-transform: none;
		text-align: left;
		white-space: normal;
	}
	.term-tip.open {
		display: flex;
	}
	.term-tip::before {
		content: '';
		position: absolute;
		left: calc(var(--arrow) - 6px);
		top: -6px;
		width: 12px;
		height: 12px;
		background: inherit;
		transform: rotate(45deg);
		border-radius: 2px;
	}
	.term-tip.above::before {
		top: auto;
		bottom: -6px;
	}
	.t {
		font-weight: 700;
		color: #ffd56b;
	}
	.e b {
		font-weight: 600;
		color: #fff;
	}
	.e {
		padding-top: 0.35rem;
		border-top: 1px solid rgba(255, 255, 255, 0.15);
		color: #c9d6e6;
		font-size: 0.875rem;
	}
	@media (prefers-reduced-motion: no-preference) {
		.term-tip.open {
			animation: tip-in 0.2s cubic-bezier(0.22, 1, 0.36, 1);
		}
		.term-tip.above.open {
			animation-name: tip-in-up;
		}
		@keyframes tip-in {
			from {
				opacity: 0;
				transform: translateY(-4px) scale(0.98);
			}
		}
		@keyframes tip-in-up {
			from {
				opacity: 0;
				transform: translateY(4px) scale(0.98);
			}
		}
	}
	@media print {
		.q {
			display: none;
		}
		.term {
			text-decoration: none;
		}
	}
</style>
