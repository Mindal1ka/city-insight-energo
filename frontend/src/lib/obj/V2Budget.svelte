<!-- Ліміт: місяць/рік/доба, баланс, економія від СЕС; редагування річного ліміту -->
<script lang="ts">
	import type { Budget } from '#lib/api-v2.ts';
	import { uah } from '#lib/api-ses.ts';
	import { num } from '#lib/format.ts';
	import Icon from '#lib/Icon.svelte';

	let {
		b,
		canEdit = false,
		onsave
	}: { b: Budget; canEdit?: boolean; onsave?: (v: number | null) => Promise<void> } = $props();

	const pctM = $derived(b.used_pct.month);
	const pctY = $derived(b.used_pct.year);
	const saved = $derived(b.without_ses_uah_year - b.paid_uah.year);

	let editing = $state(false);
	let val = $state('');
	let busy = $state(false);
	function start() {
		val = String(Math.round(b.limit_uah.year));
		editing = true;
	}
	async function save() {
		if (!onsave) return;
		const t = val.trim();
		const n = t === '' ? null : Number(t.replace(/\s/g, '').replace(',', '.'));
		if (n !== null && (!isFinite(n) || n < 0)) return;
		busy = true;
		try {
			await onsave(n);
			editing = false;
		} catch {
			/* повідомлення показує сторінка */
		} finally {
			busy = false;
		}
	}
</script>

<div class="bud">
	<div class="row">
		<div class="lbl"><span>Ліміт · місяць</span><b class="tnum">{uah(b.paid_uah.month)} <small>/ {uah(b.limit_uah.month)}</small></b></div>
		<div class="track" class:over={(pctM ?? 0) > 100}><i style="width: {Math.min(100, pctM ?? 0)}%"></i></div>
		<span class="pc tnum" class:over={(pctM ?? 0) > 100}>{pctM === null ? '—' : num(pctM) + ' %'}</span>
	</div>
	<div class="row">
		<div class="lbl"><span>Ліміт · рік</span><b class="tnum">{uah(b.paid_uah.year)} <small>/ {uah(b.limit_uah.year)}</small></b></div>
		<div class="track" class:over={(pctY ?? 0) > 100}><i style="width: {Math.min(100, pctY ?? 0)}%"></i></div>
		<span class="pc tnum" class:over={(pctY ?? 0) > 100}>{pctY === null ? '—' : num(pctY) + ' %'}</span>
	</div>

	<div class="grid tnum">
		<div class="cell">
			<span class="l">Оплачено за рік</span><b>{uah(b.paid_uah.year)}</b>
		</div>
		<div class="cell">
			<span class="l">Без СЕС</span><b>{uah(b.without_ses_uah_year)}</b>
		</div>
		<div class="cell" class:good={saved > 0}>
			<span class="l">Економія</span><b>{saved >= 0 ? '+' : '−'}{uah(Math.abs(saved))}</b>
		</div>
	</div>

	{#if canEdit && onsave}
		{#if editing}
			<form class="edit" onsubmit={(e) => { e.preventDefault(); save(); }}>
				<label class="visually-hidden" for="v2-lim">Річний ліміт, ₴</label>
				<input id="v2-lim" inputmode="numeric" bind:value={val} disabled={busy} />
				<span>₴/рік</span>
				<button class="btn btn-sm" type="submit" disabled={busy}><Icon name="check" size={16} /></button>
				<button class="btn btn-secondary btn-sm" type="button" onclick={() => (editing = false)} disabled={busy}>✕</button>
			</form>
		{:else}
			<button type="button" class="btn btn-secondary btn-sm" onclick={start}><Icon name="wallet" size={16} /> Змінити ліміт</button>
		{/if}
	{/if}
</div>

<style>
	.bud {
		display: grid;
		gap: 0.8rem;
		min-width: 0;
	}
	.row {
		display: grid;
		grid-template-columns: 1fr auto;
		grid-template-areas: 'l p' 't t';
		gap: 0.3rem 0.75rem;
		align-items: center;
	}
	.lbl {
		grid-area: l;
		display: flex;
		justify-content: space-between;
		gap: 0.5rem;
		color: var(--muted);
		min-width: 0;
	}
	.lbl b {
		color: var(--ink);
	}
	small {
		color: var(--muted);
		font-weight: 400;
	}
	.track {
		grid-area: t;
		height: 0.6rem;
		border-radius: 999px;
		background: var(--neutral-soft);
		overflow: hidden;
	}
	.track i {
		display: block;
		height: 100%;
		background: var(--ok);
		border-radius: 999px;
	}
	.track.over i {
		background: var(--bad);
	}
	.pc {
		grid-area: p;
		font-weight: 700;
		color: var(--ok);
	}
	.pc.over {
		color: var(--bad);
	}
	.grid {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 0.5rem;
	}
	.cell {
		display: grid;
		gap: 0.15rem;
		padding: 0.55rem 0.7rem;
		border-radius: 10px;
		background: var(--neutral-soft);
	}
	.cell.good {
		background: var(--ok-soft);
		color: var(--ok);
	}
	.l {
		font-size: var(--fs-xs);
		color: var(--muted);
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}
	.cell.good .l {
		color: inherit;
	}
	.cell b {
		font-size: var(--fs-lg, 1.1rem);
	}
	.edit {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
	@media (max-width: 520px) {
		.grid {
			grid-template-columns: 1fr;
		}
	}
	.edit input {
		width: 9rem;
		padding: 0.4rem 0.6rem;
		border: 1px solid var(--line);
		border-radius: 8px;
		font: inherit;
	}
	.bud > .btn {
		justify-self: start;
	}
</style>
