<!--
	Підказка, яка працює не лише з мишею: відкривається при наведенні, фокусі з клавіатури
	й дотику/кліку; закривається дотиком поза нею, Esc або прокручуванням.
	Замість атрибута title там, де підказка несе важливу інформацію.

	<Hint text="Ліміти змодельовані" />                        → значок «i»
	<Hint text="Оцінка за ринковими цінами">оцінка</Hint>      → власний вміст кнопки
-->
<script lang="ts">
	import type { Snippet } from 'svelte';
	import Icon from './Icon.svelte';

	let {
		text,
		label = 'Пояснення',
		size = 14,
		children
	}: { text: string; label?: string; size?: number; children?: Snippet } = $props();

	const id = `hint-${Math.random().toString(36).slice(2, 8)}`;
	let open = $state(false);
	let pinned = false; // відкрито кліком/дотиком — не закривати, коли миша йде геть
	let btn = $state<HTMLButtonElement | null>(null);
	let pos = $state({ left: 0, top: 0 });

	let pop = $state<HTMLElement | null>(null);

	// спливаюче вікно переносимо в <body>: його не обрізають overflow і transform батьків
	function portal(node: HTMLElement) {
		document.body.appendChild(node);
		return { destroy: () => node.remove() };
	}
	function place() {
		if (!btn) return;
		const r = btn.getBoundingClientRect();
		const w = pop?.offsetWidth || Math.min(280, window.innerWidth - 16);
		const left = Math.max(8, Math.min(r.left + r.width / 2 - w / 2, window.innerWidth - w - 8));
		pos = { left, top: r.bottom + 6 };
	}
	function show() {
		place();
		open = true;
	}
	function hide() {
		open = false;
		pinned = false;
	}
	function onclick(e: MouseEvent) {
		// підказка може стояти всередині посилання-картки: не переходити за ним
		e.preventDefault();
		e.stopPropagation();
		if (open && pinned) hide();
		else {
			show();
			pinned = true;
		}
	}

	// після появи — уточнити положення за фактичною шириною
	$effect(() => {
		if (open && pop) place();
	});

	$effect(() => {
		if (!open) return;
		const down = (e: PointerEvent) => {
			if (btn && !btn.contains(e.target as Node)) hide();
		};
		const key = (e: KeyboardEvent) => {
			if (e.key === 'Escape') hide();
		};
		const scroll = () => hide();
		document.addEventListener('pointerdown', down, true);
		document.addEventListener('keydown', key);
		window.addEventListener('scroll', scroll, { capture: true, passive: true });
		window.addEventListener('resize', scroll);
		return () => {
			document.removeEventListener('pointerdown', down, true);
			document.removeEventListener('keydown', key);
			window.removeEventListener('scroll', scroll, true);
			window.removeEventListener('resize', scroll);
		};
	});
</script>

<button
	bind:this={btn}
	type="button"
	class="hint"
	class:custom={!!children}
	aria-label={children ? undefined : label}
	aria-expanded={open}
	aria-describedby={open ? id : undefined}
	{onclick}
	onmouseenter={show}
	onmouseleave={() => !pinned && hide()}
	onfocus={show}
	onblur={hide}
>
	{#if children}{@render children()}{:else}<Icon name="info" {size} />{/if}
</button>
{#if open}
	<span use:portal bind:this={pop} role="tooltip" {id} class="hint-pop" style:left="{pos.left}px" style:top="{pos.top}px">{text}</span>
{/if}

<style>
	.hint {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		padding: 0;
		margin: 0;
		border: 0;
		background: none;
		font: inherit;
		color: inherit;
		cursor: help;
		vertical-align: middle;
		position: relative;
		border-radius: var(--r-sm);
	}
	/* зона дотику ≥ 32 px без зміни вигляду */
	.hint:not(.custom)::after {
		content: '';
		position: absolute;
		inset: -9px;
	}
	.hint-pop {
		position: fixed;
		z-index: 1000;
		width: max-content;
		max-width: min(280px, calc(100vw - 16px));
		padding: 0.5rem 0.7rem;
		border-radius: var(--r-btn);
		background: var(--ink, #0f1b2d);
		color: #fff;
		font-size: 0.8125rem;
		font-weight: 500;
		line-height: 1.4;
		text-align: left;
		white-space: normal;
		box-shadow: 0 8px 24px rgb(15 23 42 / 0.2);
		pointer-events: none;
	}
</style>
