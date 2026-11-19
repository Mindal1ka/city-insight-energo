<script lang="ts">
	// Компактна панель фільтрів СЕС: період, пошук, класи K (з лічильниками), типи закладів.
	// Спільна для мапи (/) і списку (/objects).
	import {
		K_CLASSES,
		PERIODS,
		matchQ,
		matchType,
		matchClass,
		type KClass,
		type Period,
		type SesItem
	} from './api-ses.ts';
	import { CATEGORIES } from './api-map.ts';

	let {
		items,
		period = $bindable('year'),
		classes = $bindable([]),
		types = $bindable([]),
		q = $bindable(''),
		restricted = false,
		onenter
	}: {
		items: SesItem[];
		period?: Period;
		classes?: KClass[];
		types?: string[];
		q?: string;
		restricted?: boolean;
		/** Enter у пошуку */
		onenter?: () => void;
	} = $props();

	const classCounts = $derived.by(() => {
		const out = new Map<KClass, number>();
		for (const i of items) {
			if (!i.k_class || !matchType(i, types) || !matchQ(i, q)) continue;
			out.set(i.k_class, (out.get(i.k_class) ?? 0) + 1);
		}
		return out;
	});
	const typeCounts = $derived.by(() => {
		const out = new Map<string, number>();
		for (const i of items) {
			if (!matchClass(i, classes) || !matchQ(i, q)) continue;
			out.set(i.category_short, (out.get(i.category_short) ?? 0) + 1);
		}
		return out;
	});
	const typeList = $derived(CATEGORIES.filter((c) => (typeCounts.get(c.key) ?? 0) > 0 || types.includes(c.key)));

	function toggle<T>(arr: T[], v: T): T[] {
		return arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v];
	}
	const active = $derived(classes.length + types.length + (q.trim() ? 1 : 0));
</script>

<div class="sf">
	<div class="row top">
		<div class="seg" role="radiogroup" aria-label="Період">
			{#each PERIODS as p (p.id)}
				<button
					type="button"
					role="radio"
					aria-checked={period === p.id}
					class:on={period === p.id}
					onclick={() => (period = p.id)}>{p.label}</button
				>
			{/each}
		</div>
		<label class="search">
			<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"
				><circle cx="11" cy="11" r="6.5" fill="none" stroke="currentColor" stroke-width="2" /><path
					d="m16 16 4 4"
					stroke="currentColor"
					stroke-width="2"
					stroke-linecap="round"
				/></svg
			>
			<span class="sr">Пошук об’єкта</span>
			<input
				type="search"
				placeholder="Пошук…"
				bind:value={q}
				autocomplete="off"
				onkeydown={(e) => e.key === 'Enter' && onenter?.()}
			/>
		</label>
		{#if active}
			<button type="button" class="reset" onclick={() => ((classes = []), (types = []), (q = ''))} title="Скинути фільтри"
				>✕ <span class="sr">Скинути фільтри</span></button
			>
		{/if}
	</div>
	{#if !restricted}
		<div class="row chips" role="group" aria-label="Клас ефективності">
			{#each K_CLASSES as c (c.id)}
				{@const n = classCounts.get(c.id) ?? 0}
				<button
					type="button"
					class="chip"
					class:on={classes.includes(c.id)}
					aria-pressed={classes.includes(c.id)}
					style="--c: {c.color}; --soft: {c.soft}; --ink: {c.ink}"
					onclick={() => (classes = toggle(classes, c.id))}
				>
					<span class="dot" aria-hidden="true">{c.icon}</span>{c.short}<b>{n}</b>
				</button>
			{/each}
		</div>
	{/if}
	<div class="row chips" role="group" aria-label="Тип закладу">
		{#each typeList as t (t.key)}
			<button
				type="button"
				class="chip type"
				class:on={types.includes(t.key)}
				aria-pressed={types.includes(t.key)}
				style="--c: {t.color}; --soft: #eef2f7; --ink: {t.ink}"
				onclick={() => (types = toggle(types, t.key))}
			>
				<svg class="tg" viewBox="0 0 10 10" aria-hidden="true"><path d={t.glyph} /></svg>{t.label}<b
					>{typeCounts.get(t.key) ?? 0}</b
				>
			</button>
		{/each}
	</div>
</div>

<style>
	.sf {
		display: flex;
		flex-direction: column;
		gap: 6px;
		min-width: 0;
	}
	.row {
		display: flex;
		gap: 6px;
		align-items: center;
		min-width: 0;
	}
	.chips {
		overflow-x: auto;
		scrollbar-width: none;
		padding: 2px;
		margin: -2px;
	}
	.chips::-webkit-scrollbar {
		display: none;
	}
	.seg {
		display: inline-flex;
		background: #eef2f7;
		border-radius: 999px;
		padding: 3px;
		flex: none;
	}
	.seg button {
		border: 0;
		background: none;
		padding: 6px 12px;
		border-radius: 999px;
		font: inherit;
		font-size: 0.85rem;
		font-weight: 600;
		color: #36425a;
		cursor: pointer;
		transition: background 0.2s, color 0.2s, box-shadow 0.2s;
	}
	.seg button.on {
		background: #fff;
		color: #0f1b2d;
		box-shadow: 0 1px 3px rgba(15, 35, 65, 0.18);
	}
	.search {
		flex: 1;
		min-width: 0;
		display: flex;
		align-items: center;
		gap: 6px;
		background: #eef2f7;
		border-radius: 999px;
		padding: 0 12px;
		color: #4f5b6b;
	}
	.search:focus-within {
		box-shadow: 0 0 0 2px var(--accent, #0b5cad);
	}
	.search input {
		border: 0;
		background: none;
		font: inherit;
		font-size: 0.9rem;
		padding: 7px 0;
		width: 100%;
		min-width: 0;
		outline: none;
		color: #0f1b2d;
	}
	.reset {
		flex: none;
		border: 0;
		background: #0f2f52;
		color: #fff;
		width: 32px;
		height: 32px;
		border-radius: 50%;
		cursor: pointer;
		font-size: 0.8rem;
	}
	.chip {
		flex: none;
		display: inline-flex;
		align-items: center;
		gap: 6px;
		border: 1px solid #dfe5ec;
		background: #fff;
		border-radius: 999px;
		padding: 4px 10px 4px 4px;
		font: inherit;
		font-size: 0.82rem;
		font-weight: 600;
		color: #1a2433;
		cursor: pointer;
		white-space: nowrap;
		transition: background 0.2s, border-color 0.2s, transform 0.15s;
	}
	.chip:hover {
		border-color: var(--c);
	}
	.chip:active {
		transform: scale(0.96);
	}
	.chip b {
		font-weight: 700;
		color: #4f5b6b;
		font-variant-numeric: tabular-nums;
	}
	.chip.on {
		background: var(--soft);
		border-color: var(--c);
		box-shadow: inset 0 0 0 1px var(--c);
	}
	.chip.on b {
		color: #0f1b2d;
	}
	.dot {
		display: inline-grid;
		place-items: center;
		width: 20px;
		height: 20px;
		border-radius: 50%;
		background: var(--c);
		color: var(--ink);
		font-size: 0.72rem;
		font-weight: 800;
	}
	.chip.type {
		padding-left: 8px;
	}
	.tg {
		width: 14px;
		height: 14px;
		fill: var(--c);
	}
	button:focus-visible {
		outline: 3px solid var(--focus, #ffbf47);
		outline-offset: 1px;
	}
	.sr {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip: rect(0 0 0 0);
		white-space: nowrap;
	}
</style>
