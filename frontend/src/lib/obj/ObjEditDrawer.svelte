<!-- «Редагувати дані СЕС»: бічна панель (на телефоні — знизу). Порожнє поле = «немає даних». -->
<script lang="ts">
	import { closeDialog } from '#lib/motion.ts';
	import Icon from '#lib/Icon.svelte';
	import { num } from '#lib/format.ts';
	import type { ObjSes, ObjCosts, ObjPatch } from './ObjApi.ts';

	let {
		open = $bindable(false),
		ses,
		costs,
		onsave
	}: {
		open?: boolean;
		ses: ObjSes | null;
		costs: ObjCosts | null;
		onsave: (patch: ObjPatch) => Promise<void>;
	} = $props();

	type F = { key: keyof ObjPatch; label: string; unit?: string; int?: boolean; min?: number; max?: number; kind?: 'text' | 'date'; step?: string };
	const STATION: F[] = [
		{ key: 'panels_count', label: 'Панелі', unit: 'шт', int: true, min: 1, max: 20000 },
		{ key: 'panel_w', label: 'Потужність панелі', unit: 'Вт', int: true, min: 50, max: 1000 },
		{ key: 'inverter_model', label: 'Модель інвертора', kind: 'text' },
		{ key: 'inverter_kw', label: 'Потужність інвертора', unit: 'кВт', min: 0.5, max: 5000, step: '0.1' },
		{ key: 'battery_count', label: 'Акумулятори', unit: 'шт', int: true, min: 0, max: 1000 },
		{ key: 'battery_module_kwh', label: 'Ємність модуля', unit: 'кВт·год', min: 0.1, max: 500, step: '0.01' },
		{ key: 'battery_kw', label: 'Потужність акумуляторів', unit: 'кВт', min: 0, max: 5000, step: '0.1' },
		{ key: 'connected_kw', label: 'Приєднана потужність', unit: 'кВт', min: 1, max: 20000, step: '0.1' },
		{ key: 'launched', label: 'Запущено', kind: 'date' }
	];
	const MONEY: F[] = [
		{ key: 'panels_uah', label: 'Панелі', unit: 'грн', min: 0, max: 1e9 },
		{ key: 'inverter_uah', label: 'Інвертор', unit: 'грн', min: 0, max: 1e9 },
		{ key: 'batteries_uah', label: 'Акумулятори', unit: 'грн', min: 0, max: 1e9 },
		{ key: 'install_uah', label: 'Монтаж', unit: 'грн', min: 0, max: 1e9 }
	];
	const ALL = [...STATION, ...MONEY];

	let vals = $state<Record<string, string>>({});
	let errs = $state<Record<string, string>>({});
	let saving = $state(false);
	let failed = $state<string | null>(null);
	let dlg = $state<HTMLDialogElement | null>(null);

	function fill() {
		const src: Record<string, unknown> = { ...(ses ?? {}), ...(costs ?? {}) };
		vals = Object.fromEntries(ALL.map((f) => [f.key, src[f.key] === null || src[f.key] === undefined ? '' : String(src[f.key])]));
		errs = {};
		failed = null;
	}
	$effect(() => {
		if (!dlg) return;
		if (open && !dlg.open) {
			fill();
			dlg.showModal();
		} else if (!open && dlg.open) closeDialog(dlg, window.innerWidth <= 640 ? { y: 64 } : { x: 48 });
	});

	const today = new Date().toISOString().slice(0, 10);
	function check(f: F, raw: string): string {
		const v = raw.trim();
		if (!v) return '';
		if (f.kind === 'text') return v.length > 80 ? 'Не довше 80 символів' : '';
		if (f.kind === 'date') return v > today ? 'Дата в майбутньому' : v < '2000-01-01' ? 'Надто рання дата' : '';
		const n = Number(v.replace(',', '.').replace(/\s/g, ''));
		if (!Number.isFinite(n)) return 'Введіть число';
		if (f.int && !Number.isInteger(n)) return 'Ціле число';
		if (f.min !== undefined && n < f.min) return `Від ${num(f.min, f.min % 1 ? 1 : 0)}`;
		if (f.max !== undefined && n > f.max) return `До ${num(f.max)}`;
		return '';
	}
	function parse(f: F, raw: string): string | number | null {
		const v = raw.trim();
		if (!v) return null;
		if (f.kind) return v;
		return Number(v.replace(',', '.').replace(/\s/g, ''));
	}
	const pn = (k: string) => {
		const v = (vals[k] ?? '').trim().replace(',', '.');
		return v ? Number(v) : null;
	};
	const totalKw = $derived(pn('panels_count') && pn('panel_w') ? (pn('panels_count')! * pn('panel_w')!) / 1000 : null);
	const totalKwh = $derived(pn('battery_count') && pn('battery_module_kwh') ? pn('battery_count')! * pn('battery_module_kwh')! : null);
	const totalUah = $derived(MONEY.reduce((s, f) => s + (pn(f.key) ?? 0), 0));

	async function submit(e: SubmitEvent) {
		e.preventDefault();
		const ne: Record<string, string> = {};
		for (const f of ALL) {
			const m = check(f, vals[f.key] ?? '');
			if (m) ne[f.key] = m;
		}
		errs = ne;
		const first = Object.keys(ne)[0];
		if (first) {
			dlg?.querySelector<HTMLInputElement>(`#ed-${first}`)?.focus();
			return;
		}
		const patch = Object.fromEntries(ALL.map((f) => [f.key, parse(f, vals[f.key] ?? '')])) as ObjPatch;
		saving = true;
		failed = null;
		try {
			await onsave(patch);
			open = false;
		} catch (err) {
			failed = err instanceof Error ? err.message : 'Не вдалося зберегти';
		} finally {
			saving = false;
		}
	}
</script>

{#snippet field(f: F)}
	<label class="f" class:bad={!!errs[f.key]}>
		<span class="fl">{f.label}</span>
		<span class="fi">
			<input
				id="ed-{f.key}"
				type={f.kind === 'date' ? 'date' : 'text'}
				inputmode={f.kind ? undefined : f.int ? 'numeric' : 'decimal'}
				max={f.kind === 'date' ? today : undefined}
				placeholder="немає даних"
				bind:value={vals[f.key]}
				oninput={() => errs[f.key] && (errs[f.key] = check(f, vals[f.key] ?? ''))}
				aria-invalid={!!errs[f.key]}
				aria-describedby={errs[f.key] ? `er-${f.key}` : undefined}
				autocomplete="off"
			/>
			{#if f.unit}<span class="u">{f.unit}</span>{/if}
		</span>
		{#if errs[f.key]}<span class="er" id="er-{f.key}" role="alert">{errs[f.key]}</span>{/if}
	</label>
{/snippet}

<dialog
	bind:this={dlg}
	class="drawer"
	aria-labelledby="ed-h"
	onclose={() => (open = false)}
	onclick={(e) => e.target === dlg && (open = false)}
>
	<form onsubmit={submit} novalidate>
		<header>
			<h2 id="ed-h"><Icon name="panel" size={20} /> Редагувати дані СЕС</h2>
			<button type="button" class="x" aria-label="Закрити" onclick={() => (open = false)}><Icon name="x" size={18} /></button>
		</header>
		<div class="body">
			<fieldset>
				<legend><Icon name="sun" size={16} /> Станція</legend>
				<div class="grid">
					{#each STATION as f (f.key)}{@render field(f)}{/each}
				</div>
				<p class="sum tnum">
					<span>Разом панелей <b>{totalKw !== null ? num(totalKw, 2) : '—'}</b> кВт</span>
					<span>Загальна ємність <b>{totalKwh !== null ? num(totalKwh, 2) : '—'}</b> кВт·год</span>
				</p>
			</fieldset>
			<fieldset>
				<legend><Icon name="wallet" size={16} /> Вартість</legend>
				<div class="grid">
					{#each MONEY as f (f.key)}{@render field(f)}{/each}
				</div>
				<p class="sum tnum"><span>Разом <b>{num(totalUah)}</b> грн</span></p>
			</fieldset>
			{#if failed}<p class="notice notice-error" role="alert">{failed}</p>{/if}
		</div>
		<footer>
			<button type="button" class="btn btn-secondary" onclick={() => (open = false)}>Скасувати</button>
			<button type="submit" class="btn" disabled={saving}>{saving ? 'Збереження…' : 'Зберегти'}</button>
		</footer>
	</form>
</dialog>

<style>
	.drawer {
		position: fixed;
		inset: 0 0 0 auto;
		margin: 0;
		width: min(520px, 100vw);
		max-width: 100vw;
		height: 100dvh;
		max-height: 100dvh;
		padding: 0;
		border: 0;
		background: var(--surface);
		color: var(--text);
		box-shadow: var(--shadow-lg);
	}
	/* Шухляда виїжджає з правого краю (звідки її кнопка), фон темніє паралельно — спільна крива --ease-emph */
	.drawer[open] {
		animation: slide-in var(--dur-slow) var(--ease-emph);
	}
	.drawer::backdrop {
		background: rgba(10, 31, 56, 0.45);
		animation: fade var(--dur-base) var(--ease-out);
	}
	form {
		display: flex;
		flex-direction: column;
		height: 100%;
	}
	header,
	footer {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		padding: 1rem 1.25rem;
		border-bottom: 1px solid var(--line-soft);
	}
	footer {
		border: 0;
		border-top: 1px solid var(--line-soft);
		justify-content: flex-end;
		padding-bottom: calc(1rem + var(--safe-b));
	}
	h2 {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin: 0;
		font-size: var(--fs-lg);
		flex: 1;
	}
	.x {
		width: 2.5rem;
		height: 2.5rem;
		border: 0;
		border-radius: 50%;
		background: var(--neutral-soft);
		cursor: pointer;
		font-size: 1rem;
	}
	.body {
		flex: 1;
		overflow: auto;
		padding: 1rem 1.25rem;
	}
	fieldset {
		border: 0;
		margin: 0 0 1.25rem;
		padding: 0;
	}
	legend {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		font-weight: 700;
		margin-bottom: 0.6rem;
	}
	.grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 0.75rem;
	}
	.f {
		display: grid;
		gap: 0.25rem;
		min-width: 0;
	}
	.fl {
		font-size: var(--fs-sm);
		color: var(--muted);
	}
	.fi {
		display: flex;
		align-items: center;
		border: 1px solid var(--line);
		border-radius: var(--radius-sm);
		background: var(--surface);
		transition: border-color var(--dur-fast), box-shadow var(--dur-fast);
	}
	.fi:focus-within {
		border-color: var(--accent);
		box-shadow: 0 0 0 3px var(--accent-soft);
	}
	.bad .fi {
		border-color: var(--bad);
	}
	.fi input {
		flex: 1;
		width: 100%;
		min-width: 0;
		height: auto;
		box-shadow: none;
		border-radius: var(--radius-sm);
		border: 0;
		background: transparent;
		padding: 0.6rem 0.7rem;
		font: inherit;
		font-variant-numeric: tabular-nums;
		outline: none;
	}
	.fi input:focus,
	.fi input:focus-visible {
		outline: none;
		box-shadow: none;
		border: 0;
	}
	.f {
		align-content: start;
	}
	.u {
		padding-right: 0.7rem;
		font-size: var(--fs-xs);
		color: var(--muted);
		white-space: nowrap;
	}
	.er {
		font-size: var(--fs-xs);
		color: var(--bad);
	}
	.sum {
		display: flex;
		flex-wrap: wrap;
		gap: 1rem;
		margin: 0.7rem 0 0;
		font-size: var(--fs-sm);
		color: var(--muted);
	}
	.sum b {
		color: var(--ink);
	}
	@keyframes slide-in {
		from {
			transform: translateX(48px);
			opacity: 0;
		}
	}
	@keyframes fade {
		from {
			opacity: 0;
		}
	}
	@media (max-width: 640px) {
		.drawer {
			inset: auto 0 0 0;
			width: 100vw;
			height: 92dvh;
			border-radius: var(--r-modal) var(--r-modal) 0 0;
		}
		.drawer[open] {
			animation-name: slide-up;
		}
		.grid {
			gap: 0.6rem;
		}
	}
	@keyframes slide-up {
		from {
			transform: translateY(64px);
			opacity: 0;
		}
	}
	@media (prefers-reduced-motion: reduce) {
		.drawer[open],
		.drawer::backdrop {
			animation: none;
		}
	}
</style>
