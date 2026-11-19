<script lang="ts">
	// Панель фільтрів СЕС. variant='inline' — повна панель (список /objects);
	// variant='map' — компактний рядок (пошук · період · «Фільтри (n)») + випадна панель з групами.
	import type { Snippet } from 'svelte';
	import {
		K_CLASSES,
		VISIBLE_CLASSES,
		PERIODS,
		matchQ,
		matchType,
		matchClass,
		type KClass,
		type Period,
		type SesItem
	} from './api-ses.ts';
	import { CATEGORIES } from './api-map.ts';
	import { DEPARTMENTS } from './api-v2.ts';
	import { SEASONS, type Season } from './ses-extra.ts';

	let {
		items,
		period = $bindable('year'),
		classes = $bindable([]),
		types = $bindable([]),
		q = $bindable(''),
		department = $bindable(''),
		need = $bindable(false),
		season = $bindable(null),
		restricted = false,
		onenter,
		variant = 'inline',
		shown,
		children
	}: {
		items: SesItem[];
		period?: Period;
		classes?: KClass[];
		types?: string[];
		q?: string;
		department?: string;
		need?: boolean;
		season?: Season | null;
		restricted?: boolean;
		/** Enter у пошуку */
		onenter?: () => void;
		/** 'inline' — повна панель (список); 'map' — компактний рядок + випадна панель «Фільтри» */
		variant?: 'inline' | 'map';
		/** Скільки об'єктів показано (для підвалу панелі) */
		shown?: number;
		/** Додатковий вміст підвалу панелі */
		children?: Snippet;
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
	const active = $derived(
		classes.length + types.length + (q.trim() ? 1 : 0) + (department ? 1 : 0) + (need ? 1 : 0) + (season ? 1 : 0)
	);
	/** Кількість активних фільтрів (без пошуку й періоду) */
	const nFilters = $derived(classes.length + types.length + (department ? 1 : 0) + (need ? 1 : 0) + (season ? 1 : 0));
	let open = $state(false);
	let wrap = $state<HTMLElement>();
	function resetFilters() {
		classes = [];
		types = [];
		department = '';
		need = false;
		season = null;
	}
	function onDoc(e: Event) {
		if (open && wrap && !wrap.contains(e.target as Node)) open = false;
	}
	function onKey(e: KeyboardEvent) {
		if (e.key === 'Escape' && open) open = false;
	}
	function resetAll() {
		resetFilters();
		q = '';
	}
</script>

<svelte:window onclick={onDoc} onkeydown={onKey} />

{#snippet seg()}
	<div class="seg" role="radiogroup" aria-label="Період">
		{#each PERIODS as p (p.id)}
			<button
				type="button"
				role="radio"
				aria-checked={period === p.id}
				class:on={period === p.id}
				onclick={() => ((period = p.id), (season = null))}>{p.label}</button
			>
		{/each}
	</div>
{/snippet}

{#snippet search()}
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
{/snippet}

{#snippet seasonChips()}
	{#each SEASONS as s (s.id)}
		<button
			type="button"
			class="chip plain"
			class:on={season === s.id}
			aria-pressed={season === s.id}
			style="--c: #0b5cad; --soft: #e3eefb"
			onclick={() => (season = season === s.id ? null : s.id)}>{s.label}</button
		>
	{/each}
{/snippet}

{#snippet needChip()}
	<button
		type="button"
		class="chip plain"
		class:on={need}
		aria-pressed={need}
		style="--c: #d9680f; --soft: #fdeedf"
		title="Потреба в розширенні"
		onclick={() => (need = !need)}><span class="dot" aria-hidden="true">↓</span>Потреба в розширенні</button
	>
{/snippet}

{#snippet deptSelect()}
	<select bind:value={department} aria-label="Розпорядник" class:on={!!department}>
		<option value="">Усі розпорядники</option>
		{#each DEPARTMENTS as d (d)}<option value={d}>{d}</option>{/each}
	</select>
{/snippet}

{#snippet classChips()}
	{#each VISIBLE_CLASSES as c (c.id)}
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
{/snippet}

{#snippet typeChips()}
	{#each typeList as t (t.key)}
		<button
			type="button"
			class="chip type"
			class:on={types.includes(t.key)}
			aria-pressed={types.includes(t.key)}
			style="--c: {t.color}; --soft: #eef2f7; --ink: {t.ink}"
			onclick={() => (types = toggle(types, t.key))}
		>
			<svg class="tg" viewBox="0 0 10 10" aria-hidden="true"><path d={t.glyph} /></svg>{t.label}<b>{typeCounts.get(t.key) ?? 0}</b>
		</button>
	{/each}
{/snippet}

{#if variant === 'inline'}
	<div class="sf">
		<div class="row top">
			{@render seg()}
			{@render search()}
			{#if active}
				<button type="button" class="reset" onclick={resetAll} title="Скинути фільтри"
					>✕ <span class="sr">Скинути фільтри</span></button
				>
			{/if}
		</div>
		{#if !restricted}
			<div class="row chips" role="group" aria-label="Сезон">
				{@render seasonChips()}
				{@render needChip()}
			</div>
			<div class="row chips" role="group" aria-label="Розпорядник">
				{@render deptSelect()}
			</div>
			<div class="row chips" role="group" aria-label="Клас ефективності">
				{@render classChips()}
			</div>
		{/if}
		<div class="row chips" role="group" aria-label="Тип закладу">
			{@render typeChips()}
		</div>
	</div>
{:else}
	<div class="mf" bind:this={wrap}>
		<div class="mbar">
			{@render search()}
			<div class="segw">{@render seg()}</div>
			<button
				type="button"
				class="fbtn"
				class:on={open || nFilters > 0}
				aria-expanded={open}
				aria-controls="mf-panel"
				onclick={() => (open = !open)}
			>
				<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"
					><path d="M4 6h16M7 12h10M10 18h4" stroke="currentColor" stroke-width="2" stroke-linecap="round" fill="none" /></svg
				>Фільтри{#if nFilters}<span class="n">{nFilters}</span>{/if}
			</button>
		</div>

		{#if nFilters}
			<ul class="active" aria-label="Активні фільтри">
				{#if season}<li><button type="button" onclick={() => (season = null)}>{season} <span aria-hidden="true">✕</span><span class="sr">прибрати</span></button></li>{/if}
				{#if department}<li><button type="button" onclick={() => (department = '')}>{department} <span aria-hidden="true">✕</span><span class="sr">прибрати</span></button></li>{/if}
				{#if need}<li><button type="button" onclick={() => (need = false)}>Потреба в розширенні <span aria-hidden="true">✕</span><span class="sr">прибрати</span></button></li>{/if}
				{#each classes as c (c)}<li><button type="button" onclick={() => (classes = classes.filter((x) => x !== c))}>{c} <span aria-hidden="true">✕</span><span class="sr">прибрати</span></button></li>{/each}
				{#each types as t (t)}<li><button type="button" onclick={() => (types = types.filter((x) => x !== t))}>{CATEGORIES.find((c) => c.key === t)?.label ?? t} <span aria-hidden="true">✕</span><span class="sr">прибрати</span></button></li>{/each}
			</ul>
		{/if}

		{#if open}
			<div class="panel" id="mf-panel" role="dialog" aria-label="Фільтри">
				<div class="sec mseg"><h3>Період</h3>{@render seg()}</div>
				{#if !restricted}
					<div class="sec"><h3>Сезон</h3><div class="chips wrapc">{@render seasonChips()}</div></div>
					<div class="sec"><h3>Розпорядник</h3>{@render deptSelect()}</div>
				{/if}
				<div class="sec"><h3>Тип закладу</h3><div class="chips wrapc">{@render typeChips()}</div></div>
				{#if !restricted}
					<div class="sec"><h3>Покриття сонцем</h3><div class="chips wrapc">{@render classChips()}</div></div>
					<div class="sec"><h3>Потреба в розширенні</h3><div class="chips wrapc">{@render needChip()}</div></div>
				{/if}
				<div class="foot">
					<button type="button" class="rst" onclick={resetFilters} disabled={!nFilters}>Скинути</button>
					{#if shown != null}<span class="cnt">Показано <b>{shown}</b> з {items.length}</span>{/if}
					<a class="lst" href="/objects">Список →</a>
				</div>
				{#if children}<div class="extra">{@render children()}</div>{/if}
			</div>
		{/if}
	</div>
{/if}

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
	.chip.plain {
		padding: 5px 12px;
	}
	.chip.plain .dot {
		margin-left: -6px;
	}
	select {
		flex: none;
		max-width: 220px;
		border: 1px solid #dfe5ec;
		background: #fff;
		border-radius: 999px;
		padding: 5px 10px;
		font: inherit;
		font-size: 0.82rem;
		font-weight: 600;
		color: #1a2433;
	}
	select.on {
		border-color: #0b5cad;
		background: #e3eefb;
	}
	.chip.type {
		padding-left: 8px;
	}
	.tg {
		width: 14px;
		height: 14px;
		fill: var(--c);
	}
	button:focus-visible,
	a:focus-visible {
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

	/* --- variant="map" --- */
	.mf {
		position: relative;
		display: flex;
		flex-direction: column;
		align-items: flex-end;
		gap: 6px;
		min-width: 0;
		width: 100%;
	}
	.mbar,
	.panel {
		background: rgba(255, 255, 255, 0.95);
		-webkit-backdrop-filter: saturate(1.5) blur(12px);
		backdrop-filter: saturate(1.5) blur(12px);
		box-shadow: 0 2px 6px rgba(15, 35, 65, 0.08), 0 12px 32px -14px rgba(15, 35, 65, 0.35);
		border-radius: 16px;
	}
	.mbar {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 6px;
		width: 100%;
		min-width: 0;
	}
	.mbar .search {
		min-width: 80px;
	}
	.segw {
		display: contents;
	}
	.fbtn {
		flex: none;
		display: inline-flex;
		align-items: center;
		gap: 6px;
		border: 1px solid #dfe5ec;
		background: #fff;
		border-radius: 999px;
		padding: 7px 14px;
		font: inherit;
		font-size: 0.88rem;
		font-weight: 700;
		color: #1a2433;
		cursor: pointer;
	}
	.fbtn.on {
		background: #e3eefb;
		border-color: #0b5cad;
		color: #0b3f7a;
	}
	.fbtn .n {
		display: inline-grid;
		place-items: center;
		min-width: 20px;
		height: 20px;
		padding: 0 5px;
		border-radius: 999px;
		background: #0b5cad;
		color: #fff;
		font-size: 0.74rem;
	}
	.active {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-wrap: wrap;
		justify-content: flex-end;
		gap: 5px;
	}
	.active button {
		border: 0;
		border-radius: 999px;
		padding: 4px 10px;
		background: #0f2f52;
		color: #fff;
		font: inherit;
		font-size: 0.76rem;
		font-weight: 600;
		cursor: pointer;
		box-shadow: 0 2px 8px rgba(15, 35, 65, 0.25);
	}
	.active button:hover {
		background: #1f4f84;
	}
	.panel {
		position: absolute;
		top: 54px;
		right: 0;
		z-index: 10;
		width: min(440px, 100%);
		max-height: calc(100vh - 200px);
		overflow-y: auto;
		padding: 14px;
		display: flex;
		flex-direction: column;
		gap: 12px;
	}
	.sec h3 {
		margin: 0 0 6px;
		font-size: 0.72rem;
		font-weight: 700;
		color: #4f5b6b;
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}
	.sec select {
		max-width: 100%;
	}
	.wrapc {
		flex-wrap: wrap;
		overflow: visible;
		display: flex;
		gap: 6px;
		padding: 0;
		margin: 0;
	}
	.mseg {
		display: none;
	}
	.foot {
		display: flex;
		align-items: center;
		gap: 10px;
		padding-top: 10px;
		border-top: 1px solid #e6ebf1;
		font-size: 0.8rem;
		color: #4f5b6b;
	}
	.foot .cnt {
		margin-left: auto;
		font-variant-numeric: tabular-nums;
	}
	.foot .cnt b {
		color: #0f1b2d;
	}
	.rst {
		border: 1px solid #dfe5ec;
		background: #fff;
		border-radius: 999px;
		padding: 5px 14px;
		font: inherit;
		font-weight: 700;
		color: #1a2433;
		cursor: pointer;
	}
	.rst:disabled {
		opacity: 0.45;
		cursor: default;
	}
	.lst {
		font-weight: 700;
		color: var(--accent, #0b5cad);
		text-decoration: none;
	}
	.lst:hover {
		text-decoration: underline;
	}
	.extra {
		font-size: 0.8rem;
	}
	@media (max-width: 640px) {
		.mbar .segw {
			display: none;
		}
		.mseg {
			display: block;
		}
		.panel {
			max-height: 70vh;
		}
	}
</style>
