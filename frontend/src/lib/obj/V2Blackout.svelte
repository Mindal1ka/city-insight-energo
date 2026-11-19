<!-- Блекаут: години автономії (акумулятор / + сонце / + генератор) і генератор. 403 — блок не показується. -->
<script lang="ts">
	import { fetchBlackout, updateGenerator, addFuel, deleteFuel, type Blackout } from '#lib/api-v2.ts';
	import { errMessage, ApiError } from '#lib/api.ts';
	import { uah } from '#lib/api-ses.ts';
	import { num } from '#lib/format.ts';
	import Icon from '#lib/Icon.svelte';

	let { id, canEdit = false, available = $bindable(false) }: { id: number; canEdit?: boolean; available?: boolean } = $props();

	let b = $state<Blackout | null>(null);
	let hidden = $state(false);
	let loaded = $state(false);

	async function load(oid: number) {
		try {
			const r = await fetchBlackout(oid);
			if (oid === id) {
				b = r;
				available = true;
			}
		} catch (e) {
			if (oid !== id) return;
			b = null;
			if (e instanceof ApiError) hidden = true;
		} finally {
			if (oid === id) loaded = true;
		}
	}
	$effect(() => {
		b = null;
		available = false;
		hidden = false;
		loaded = false;
		load(id);
	});

	const horizon = $derived(b?.horizon_h ?? 48);
	const bars = $derived(
		b
			? [
					{ key: 'bat', label: 'Лише акумулятор', icon: 'battery', v: b.hours_battery },
					{ key: 'sun', label: '+ сонце', icon: 'sun', v: b.hours_battery_sun },
					...(b.generator && b.hours_with_generator != null
						? [{ key: 'gen', label: '+ генератор', icon: 'bolt', v: b.hours_with_generator }]
						: [])
				]
			: []
	);
	const hrs = (v: number) => (v >= horizon ? `${horizon}+` : num(v, 1));

	// --- редагування ---
	let editing = $state(false);
	let kw = $state('');
	let tank = $state('');
	let fuel = $state('');
	let cost = $state('');
	let bought = $state('');
	let doc = $state('');
	let saving = $state(false);
	let err = $state<string | null>(null);
	function openForm() {
		kw = b?.generator ? String(b.generator.generator_kw) : '';
		tank = b?.generator ? String(b.generator.tank_l) : '';
		fuel = b?.generator?.fuel ?? 'дизель';
		cost = b?.generator?.cost_uah != null ? String(b.generator.cost_uah) : '';
		bought = b?.generator?.bought ?? '';
		doc = b?.generator?.doc ?? '';
		err = null;
		editing = true;
	}
	async function save(ev: SubmitEvent) {
		ev.preventDefault();
		const k = Number(kw.replace(',', '.'));
		const t = Number(tank.replace(',', '.'));
		if (!(k > 0) || !(t >= 0)) {
			err = 'Вкажіть потужність і бак';
			return;
		}
		saving = true;
		err = null;
		try {
			const c = cost.trim() ? Number(cost.replace(/\s/g, '').replace(',', '.')) : null;
			if (c != null && !(c >= 0)) {
				err = 'Вартість — число';
				saving = false;
				return;
			}
			await updateGenerator(id, {
				generator_kw: k,
				tank_l: t,
				fuel: fuel.trim() || undefined,
				cost_uah: c,
				bought: bought || null,
				doc: doc.trim() || null
			});
			await load(id);
			editing = false;
		} catch (e) {
			err = errMessage(e);
		} finally {
			saving = false;
		}
	}

	// --- журнал пального ---
	const today = new Date().toISOString().slice(0, 10);
	let fDate = $state(today);
	let fLit = $state('');
	let fUah = $state('');
	let fNote = $state('');
	let fBusy = $state(false);
	let fErr = $state<string | null>(null);
	const fuelPrice = $derived((b?.assumptions?.fuel_price_uah_l as number | undefined) ?? 101);
	async function addEntry(ev: SubmitEvent) {
		ev.preventDefault();
		const l = Number(fLit.replace(',', '.'));
		const u = fUah.trim() ? Number(fUah.replace(/\s/g, '').replace(',', '.')) : 0;
		if (!(l > 0) || !(u >= 0)) {
			fErr = 'Вкажіть літри (і суму, якщо знаєте)';
			return;
		}
		fBusy = true;
		fErr = null;
		try {
			b = await addFuel(id, { date: fDate, liters: l, uah: u || undefined, note: fNote.trim() || undefined });
			fLit = fUah = fNote = '';
		} catch (e) {
			fErr = errMessage(e);
		} finally {
			fBusy = false;
		}
	}
	async function removeEntry(eid: number) {
		if (!confirm('Видалити запис про пальне?')) return;
		try {
			b = await deleteFuel(id, eid);
		} catch (e) {
			fErr = errMessage(e);
		}
	}
	const dmy = (d: string) => d.split('-').reverse().join('.');
</script>

{#if !hidden && loaded && b}
	<div class="panel bo">
		<div class="bars" role="img" aria-label="Години автономії">
			{#each bars as r (r.key)}
				<div class="line">
					<span class="lb"><Icon name={r.icon as 'sun'} size={15} /> {r.label}</span>
					<span class="track"><span class="fill {r.key}" style="width: {Math.min(100, (r.v / horizon) * 100)}%"></span></span>
					<b class="tnum">{hrs(r.v)} <small>год</small></b>
				</div>
			{/each}
		</div>

		<div class="gen">
			{#if b.generator}
				{@const g = b.generator}
				<div class="g-head">
					<span class="g-t"><Icon name="bolt" size={16} /> Генератор</span>
					{#if g.source === 'МОК'}<span class="mok" title="Демонстраційні дані">МОК</span>{/if}
					{#if canEdit && !editing}<button type="button" class="btn btn-secondary btn-sm" onclick={openForm}>Змінити</button>{/if}
				</div>
				<div class="facts tnum">
					<span><b>{num(g.generator_kw, 1)}</b> кВт</span>
					<span>{g.fuel}</span>
					<span>бак <b>{num(g.tank_l)}</b> л</span>
					{#if b.generator_cost_uah_kwh != null}<span><b>{num(b.generator_cost_uah_kwh, 1)}</b> грн/кВт·год</span>{/if}
					{#if b.fuel_l_per_day != null}<span><b>{num(b.fuel_l_per_day, 1)}</b> л/добу</span>{/if}
				</div>
				{#if b.generator_charges_battery}
					<p class="chg">
						<Icon name="battery" size={15} /> заряджає акумулятор через інвертор
						{#if b.generator_full_charge_h != null}<span class="tnum">· повний заряд ≈ {num(b.generator_full_charge_h, 1)} год</span>{/if}
					</p>
				{/if}
				{#if b.money}
					{@const m = b.money}
					<div class="money">
						<div class="mc">
							<span class="ml">Вкладено в генератор {#if m.capex_source === 'МОК'}<span class="mok sm" title="Оцінка за ринковими цінами: введіть фактичну вартість">оцінка</span>{/if}</span>
							<b class="tnum">{uah(m.capex_uah)}</b>
							<span class="mn">
								{#if m.bought}куплено {dmy(m.bought)}{/if}
								{#if m.doc}{m.bought ? ' · ' : ''}{m.doc}{/if}
								{#if !m.bought && !m.doc && m.capex_source === 'МОК'}ціна з АВР і монтажем, листопад 2026{/if}
							</span>
						</div>
						<div class="mc">
							<span class="ml">Пальне за {m.fuel_year} {#if m.fuel_source === 'МОК'}<span class="mok sm" title="Оцінка: {b.assumptions?.fuel_price_uah_l ?? 101} грн/л, ~150 мотогодин на рік">оцінка</span>{/if}</span>
							<b class="tnum">{uah(m.fuel_year_uah)}</b>
							<span class="mn tnum">{num(m.fuel_year_l)} л{m.fuel_source === 'журнал' ? ` · ${m.fuel_entries} ${m.fuel_entries === 1 ? 'запис' : 'записи(ів)'} у журналі` : ' · журнал порожній'}</span>
						</div>
					</div>

					<div class="log">
						<h4>Журнал пального</h4>
						{#if b.fuel_log.length}
							<table>
								<thead><tr><th>Дата</th><th class="r">Літри</th><th class="r">Сума</th><th>Примітка</th>{#if canEdit}<th></th>{/if}</tr></thead>
								<tbody>
									{#each b.fuel_log as e (e.id)}
										<tr>
											<td class="tnum">{dmy(e.date)}</td>
											<td class="r tnum">{num(e.liters)}</td>
											<td class="r tnum">{uah(e.uah)}</td>
											<td class="note">{e.note}</td>
											{#if canEdit}<td class="r"><button type="button" class="x" aria-label="Видалити запис" onclick={() => removeEntry(e.id)}>×</button></td>{/if}
										</tr>
									{/each}
								</tbody>
							</table>
						{:else}
							<p class="log-empty">Записів немає — витрати на пальне показано оцінкою.</p>
						{/if}
						{#if canEdit}
							<form class="form" onsubmit={addEntry}>
								<label>Дата<input type="date" bind:value={fDate} max={today} required /></label>
								<label>Літри<input inputmode="decimal" bind:value={fLit} required /></label>
								<label>Сума, грн<input inputmode="decimal" bind:value={fUah} placeholder={fLit ? String(Math.round(Number(fLit.replace(',', '.')) * fuelPrice)) : ''} /></label>
								<label class="wide">Примітка<input bind:value={fNote} placeholder="напр. накладна №…" /></label>
								<button class="btn btn-sm" type="submit" disabled={fBusy}>{fBusy ? '…' : 'Додати'}</button>
								{#if fErr}<p class="err" role="alert">{fErr}</p>{/if}
							</form>
						{/if}
					</div>
				{/if}
			{:else}
				<div class="g-head">
					<span class="g-t none"><Icon name="bolt" size={16} /> Генератора немає</span>
					{#if canEdit && !editing}<button type="button" class="btn btn-sm" onclick={openForm}>Додати</button>{/if}
				</div>
			{/if}

			{#if canEdit && editing}
				<form class="form" onsubmit={save}>
					<label>кВт<input inputmode="decimal" bind:value={kw} required /></label>
					<label>Бак, л<input inputmode="decimal" bind:value={tank} required /></label>
					<label>Паливо<input bind:value={fuel} /></label>
					<label>Вартість, грн<input inputmode="decimal" bind:value={cost} placeholder="оцінка, якщо порожньо" /></label>
					<label>Дата покупки<input type="date" bind:value={bought} /></label>
					<label class="wide">Документ<input bind:value={doc} placeholder="Prozorro UA-… або рахунок" /></label>
					<button class="btn btn-sm" type="submit" disabled={saving}>{saving ? '…' : 'Зберегти'}</button>
					<button class="btn btn-secondary btn-sm" type="button" onclick={() => (editing = false)}>Скасувати</button>
					{#if err}<p class="err" role="alert">{err}</p>{/if}
				</form>
			{/if}
		</div>
	</div>
{/if}

<style>
	.bo {
		display: grid;
		gap: 1rem;
		padding: 1rem;
	}
	.bars {
		display: grid;
		gap: 0.6rem;
	}
	.line {
		display: grid;
		grid-template-columns: 9.5rem 1fr 4.5rem;
		align-items: center;
		gap: 0.6rem;
	}
	.lb {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		font-size: var(--fs-sm);
		color: var(--muted);
	}
	.track {
		height: 0.9rem;
		border-radius: 999px;
		background: var(--neutral-soft);
		overflow: hidden;
	}
	.fill {
		display: block;
		height: 100%;
		border-radius: 999px;
	}
	.fill.bat {
		background: var(--bat, #6d4fc2);
	}
	.fill.sun {
		background: var(--sun-strong);
	}
	.fill.gen {
		background: var(--ok);
	}
	.line b {
		text-align: right;
		color: var(--ink);
	}
	small {
		color: var(--muted);
		font-weight: 400;
	}
	.gen {
		display: grid;
		gap: 0.5rem;
		padding-top: 0.8rem;
		border-top: 1px solid var(--line);
	}
	.g-head {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.5rem;
	}
	.g-t {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		font-weight: 700;
		color: var(--ink);
		margin-right: auto;
	}
	.g-t.none {
		color: var(--muted);
	}
	.mok {
		padding: 0.1rem 0.55rem;
		border-radius: 999px;
		font-size: 0.75rem;
		font-weight: 700;
		letter-spacing: 0.06em;
		background: var(--sun-soft);
		color: var(--sun-ink);
		border: 1px dashed #d08a1c;
	}
	.facts {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem 1.1rem;
		color: var(--muted);
		font-size: var(--fs-sm);
	}
	.facts b {
		color: var(--ink);
	}
	.chg {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.35rem;
		margin: 0;
		font-size: var(--fs-sm);
		color: var(--ok);
		font-weight: 600;
	}
	.form {
		display: flex;
		flex-wrap: wrap;
		align-items: flex-end;
		gap: 0.5rem;
	}
	.form label {
		display: grid;
		gap: 0.15rem;
		font-size: var(--fs-xs);
		color: var(--muted);
	}
	.form input {
		width: 6.5rem;
		min-height: 2.25rem;
		padding: 0 0.5rem;
		border: 1px solid var(--line);
		border-radius: 8px;
		font: inherit;
		background: var(--surface);
		color: var(--ink);
	}
	.money {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		border: 1px solid var(--card-line);
		border-radius: var(--radius);
		overflow: hidden;
	}
	.mc {
		display: grid;
		gap: 0.2rem;
		padding: 0.7rem 0.9rem;
	}
	.mc + .mc {
		border-left: 1px solid var(--card-line);
	}
	.ml {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		font-size: var(--fs-sm);
		color: var(--muted);
		font-weight: 600;
	}
	.mc b {
		font-size: 1.35rem;
		color: var(--ink);
	}
	.mn {
		font-size: var(--fs-xs);
		color: var(--muted);
	}
	.mok.sm {
		font-size: 0.68rem;
		padding: 0 0.4rem;
		letter-spacing: 0;
	}
	.log h4 {
		margin: 0.3rem 0 0.4rem;
		font-size: var(--fs-sm);
		color: var(--text-2);
	}
	.log table {
		width: 100%;
		border-collapse: collapse;
		font-size: var(--fs-sm);
		margin-bottom: 0.6rem;
	}
	.log th {
		text-align: left;
		font-size: var(--fs-xs);
		color: var(--muted);
		font-weight: 600;
		padding: 0.3rem 0.4rem;
		border-bottom: 1px solid var(--line);
	}
	.log td {
		padding: 0.35rem 0.4rem;
		border-bottom: 1px solid var(--line-soft);
	}
	.log .r {
		text-align: right;
	}
	.log .note {
		color: var(--muted);
	}
	.x {
		border: 0;
		background: none;
		color: var(--muted);
		font-size: 1.1rem;
		cursor: pointer;
		line-height: 1;
	}
	.x:hover {
		color: var(--bad);
	}
	.log-empty {
		margin: 0 0 0.6rem;
		font-size: var(--fs-sm);
		color: var(--muted);
	}
	.form .wide input {
		width: 13rem;
	}
	.err {
		flex-basis: 100%;
		margin: 0;
		color: var(--bad);
		font-size: var(--fs-sm);
	}
	@media (max-width: 640px) {
		.money {
			grid-template-columns: 1fr;
		}
		.mc + .mc {
			border-left: 0;
			border-top: 1px solid var(--card-line);
		}
		.line {
			grid-template-columns: 1fr 4rem;
		}
		.track {
			grid-column: 1 / -1;
			grid-row: 2;
		}
	}
</style>
