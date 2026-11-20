<!--
	«Детальніше» — розкривний блок для другорядних даних (прогресивне розкриття).
	Плавна анімація висоти; закритий вміст не фокусується (inert). При друці — завжди відкритий.

	ВИКОРИСТАННЯ
	  import Disclosure from '#lib/Disclosure.svelte';
	  <Disclosure summary="Детальніше про розрахунок">
	    <p>…таблиця, формули, технічні цифри…</p>
	  </Disclosure>
	  <Disclosure summary="Усі показники" bind:open={showAll}>…</Disclosure>

	Props: summary?:string = 'Детальніше', open?:boolean = false (bindable), hint?:string (сірий підпис
	праворуч від заголовка, напр. «5 показників»), class?:string, children
-->
<script lang="ts">
	import type { Snippet } from 'svelte';

	let {
		summary = 'Детальніше',
		open = $bindable(false),
		hint = '',
		class: klass = '',
		children
	}: {
		summary?: string;
		open?: boolean;
		hint?: string;
		class?: string;
		children: Snippet;
	} = $props();

	const uid = `disc-${Math.random().toString(36).slice(2, 9)}`;
</script>

<div class="disc {klass}" class:open>
	<button
		type="button"
		class="disc-btn"
		aria-expanded={open}
		aria-controls={uid}
		onclick={() => (open = !open)}
	>
		<span class="disc-ico" aria-hidden="true">
			<svg width="14" height="14" viewBox="0 0 14 14"
				><path d="M3 5.25 7 9.25l4-4" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" /></svg
			>
		</span>
		<span class="disc-sum">{summary}</span>
		{#if hint}<span class="disc-hint">{hint}</span>{/if}
	</button>
	<div class="disc-panel" id={uid} inert={!open}>
		<div class="disc-clip">
			<div class="disc-body">
				{@render children()}
			</div>
		</div>
	</div>
</div>

<style>
	.disc {
		border-top: 1px solid var(--line-soft, #e6ebf1);
		margin-top: 0.75rem;
	}
	.disc-btn {
		display: flex;
		align-items: center;
		gap: 0.55rem;
		width: 100%;
		padding: 0.7rem 0.15rem;
		border: 0;
		background: none;
		font: inherit;
		font-weight: 600;
		color: var(--accent);
		cursor: pointer;
		text-align: left;
		border-radius: var(--r-btn);
	}
	.disc-btn:hover {
		color: var(--accent-dark);
	}
	.disc-btn:hover .disc-ico {
		background: var(--accent-soft);
	}
	.disc-ico {
		display: grid;
		place-items: center;
		width: 1.5rem;
		height: 1.5rem;
		border-radius: 50%;
		border: 1px solid currentColor;
		flex: none;
		transition:
			transform var(--dur-base, 240ms) var(--ease-out, ease),
			background var(--dur-fast, 150ms);
	}
	.open .disc-ico {
		transform: rotate(180deg);
	}
	.disc-sum {
		flex: 1;
	}
	.disc-hint {
		font-weight: 400;
		font-size: 0.875rem;
		color: var(--muted);
	}
	.disc-panel {
		display: grid;
		grid-template-rows: 0fr;
		visibility: hidden;
		transition:
			grid-template-rows var(--dur-slow, 420ms) var(--ease-out, ease),
			visibility 0s linear var(--dur-slow, 420ms);
	}
	.open .disc-panel {
		grid-template-rows: 1fr;
		visibility: visible;
		transition:
			grid-template-rows var(--dur-slow, 420ms) var(--ease-out, ease),
			visibility 0s;
	}
	.disc-clip {
		overflow: hidden;
		min-height: 0;
	}
	.disc-body {
		padding: 0.25rem 0.15rem 0.9rem;
		opacity: 0;
		transform: translateY(-6px);
		transition:
			opacity var(--dur-base, 240ms) var(--ease-out, ease),
			transform var(--dur-base, 240ms) var(--ease-out, ease);
	}
	.open .disc-body {
		opacity: 1;
		transform: none;
		transition-delay: 80ms;
	}
	@media (prefers-reduced-motion: reduce) {
		.disc-panel,
		.open .disc-panel,
		.disc-body,
		.open .disc-body,
		.disc-ico {
			transition: none;
		}
	}
	@media print {
		.disc-btn {
			display: none;
		}
		.disc-panel {
			grid-template-rows: 1fr;
			visibility: visible;
		}
		.disc-body {
			opacity: 1;
			transform: none;
		}
	}
</style>
