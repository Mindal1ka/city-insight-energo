<!-- Блекаут: години автономії (акумулятор / + сонце / + генератор) і генератор. 403 — блок не показується. -->
<script lang="ts">
	import { fetchBlackout, updateGenerator, type Blackout } from '#lib/api-v2.ts';
	import { errMessage, ApiError } from '#lib/api.ts';
	import { uah } from '#lib/api-ses.ts';
	import { num } from '#lib/format.ts';
	import Icon from '#lib/Icon.svelte';

	let { id, canEdit = false }: { id: number; canEdit?: boolean } = $props();

	let b = $state<Blackout | null>(null);
	let hidden = $state(false);
	let loaded = $state(false);

	async function load(oid: number) {
		try {
			const r = await fetchBlackout(oid);
			if (oid === id) b = r;
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
	let saving = $state(false);
	let err = $state<string | null>(null);
	function openForm() {
		kw = b?.generator ? String(b.generator.generator_kw) : '';
		tank = b?.generator ? String(b.generator.tank_l) : '';
		fuel = b?.generator?.fuel ?? 'дизель';
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
			await updateGenerator(id, { generator_kw: k, tank_l: t, fuel: fuel.trim() || undefined });
			await load(id);
			editing = false;
		} catch (e) {
			err = errMessage(e);
		} finally {
			saving = false;
		}
	}
</script>

{#if !hidden && loaded && b}
	<section class="sec" aria-labelledby="bo-h">
	<h2 id="bo-h"><span class="si" aria-hidden="true"><Icon name="battery" size={18} /></span>Блекаут</h2>
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
					<button class="btn btn-sm" type="submit" disabled={saving}>{saving ? '…' : 'Зберегти'}</button>
					<button class="btn btn-secondary btn-sm" type="button" onclick={() => (editing = false)}>Скасувати</button>
					{#if err}<p class="err" role="alert">{err}</p>{/if}
				</form>
			{/if}
		</div>
	</div>
	</section>
{/if}

<style>
	.sec {
		display: grid;
		gap: 0.75rem;
		min-width: 0;
	}
	h2 {
		display: flex;
		align-items: center;
		gap: 0.55rem;
		margin: 0;
		font-size: var(--fs-xl);
		color: var(--ink);
	}
	.si {
		display: grid;
		place-items: center;
		width: 2rem;
		height: 2rem;
		border-radius: 9px;
		background: var(--sun-soft);
		color: var(--sun-ink);
	}
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
	.err {
		flex-basis: 100%;
		margin: 0;
		color: var(--bad);
		font-size: var(--fs-sm);
	}
	@media (max-width: 640px) {
		.line {
			grid-template-columns: 1fr 4rem;
		}
		.track {
			grid-column: 1 / -1;
			grid-row: 2;
		}
	}
</style>
