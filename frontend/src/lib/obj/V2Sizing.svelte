<!-- Скільки доставити (лише кВт·год): споживання → потрібна станція → поточна → доставити -->
<script lang="ts">
	import type { Sizing } from '#lib/api-v2.ts';
	import { kText, uah } from '#lib/api-ses.ts';
	import { num } from '#lib/format.ts';
	import Icon from '#lib/Icon.svelte';

	let { s, id, hasStation = false, surplus = false }: { s: Sizing; id: string | number; hasStation?: boolean; surplus?: boolean } = $props();
</script>

<div class="panel siz">
	{#if s.cons_kwh_month_avg != null}
		<p class="cons tnum"><Icon name="plug" size={16} /> Споживання ≈ <b>{num(s.cons_kwh_month_avg)}</b> кВт·год/міс</p>
	{/if}
	{#if s.need}
		{#if s.need_kw != null || s.need_battery_kwh != null}
			<div class="need tnum">
				<span class="l">Потрібна станція</span>
				<div class="row">
					{#if s.need_kw != null}<span class="it sun"><Icon name="panel" size={18} /><b>{num(s.need_kw, 1)}</b> <small>кВт панелей</small></span>{/if}
					{#if s.need_kw != null && s.need_battery_kwh != null}<span class="pl">+</span>{/if}
					{#if s.need_battery_kwh != null}<span class="it bat"><Icon name="battery" size={18} /><b>{num(s.need_battery_kwh, 1)}</b> <small>кВт·год акумулятор</small></span>{/if}
				</div>
				{#if hasStation && (s.current_kw != null || s.current_battery_kwh != null)}
					<p class="cur">
						Зараз: {num(s.current_kw ?? 0, 1)} кВт · {num(s.current_battery_kwh ?? 0, 1)} кВт·год
					</p>
				{/if}
			</div>
		{/if}
		<div class="big tnum">
			<span class="l">Доставити</span>
			<span class="adds">
				{#if s.add_kw > 0}<span class="a"><span class="p">+</span><b>{num(s.add_kw, 1)}</b><small>кВт</small></span>{/if}
				{#if (s.add_battery_kwh ?? 0) > 0}<span class="a bat"><span class="p">+</span><b>{num(s.add_battery_kwh, 1)}</b><small>кВт·год</small></span>{/if}
			</span>
		</div>
		<div class="grid tnum">
			{#if s.k_after != null}<div class="cell"><span class="l">Покриття після</span><b>{kText(s.k_after)}</b></div>{/if}
			{#if s.capex_uah !== undefined}<div class="cell"><span class="l">Вартість</span><b>{uah(s.capex_uah)}</b></div>{/if}
			{#if s.saved_uah_year !== undefined}<div class="cell good"><span class="l">Економія/рік</span><b>{uah(s.saved_uah_year)}</b></div>{/if}
			{#if s.payback_years != null}<div class="cell"><span class="l">Окупність</span><b>{num(s.payback_years, 1)} <small>р.</small></b></div>{/if}
		</div>
		<a class="btn btn-sun btn-sm" href="/appeals?building={id}&type=expand&kw={s.add_kw}"><Icon name="sun" size={16} /> Подати звернення</a>
	{:else if hasStation}
		<p class="ok"><Icon name="check" size={15} stroke={2.4} /> потужності достатньо</p>
	{/if}
	{#if surplus}
		<a class="btn btn-secondary btn-sm" href="/appeals?building={id}&type=surplus"><Icon name="grid" size={16} /> Передати надлишок</a>
	{/if}
</div>

<style>
	.siz {
		display: grid;
		gap: 0.8rem;
		padding: 1rem;
		justify-items: start;
	}
	.cons {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		margin: 0;
		color: var(--muted);
	}
	.cons b {
		color: var(--ink);
	}
	.need {
		display: grid;
		gap: 0.35rem;
	}
	.row,
	.adds {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 0.4rem 0.8rem;
	}
	.it {
		display: inline-flex;
		align-items: baseline;
		gap: 0.35rem;
	}
	.it b {
		font-size: var(--fs-xl);
	}
	.it.sun {
		color: var(--sun-ink);
	}
	.it.bat,
	.a.bat {
		color: var(--bat, #6d4fc2);
	}
	.pl {
		color: var(--muted);
		font-weight: 700;
	}
	.cur {
		margin: 0;
		font-size: var(--fs-sm);
		color: var(--muted);
	}
	.big {
		display: grid;
		gap: 0.2rem;
	}
	.a {
		display: inline-flex;
		align-items: baseline;
		gap: 0.25rem;
		color: var(--sun-ink);
	}
	.a.bat {
		color: var(--bat, #6d4fc2);
	}
	.a .p,
	.a b {
		font-size: 2.2rem;
		font-weight: 800;
		line-height: 1;
	}
	small {
		color: var(--muted);
		font-weight: 400;
	}
	.grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
		gap: 0.5rem;
		width: 100%;
	}
	.cell {
		display: grid;
		gap: 0.15rem;
		padding: 0.55rem 0.7rem;
		border-radius: var(--r-card);
		background: var(--neutral-soft);
	}
	.cell.good {
		background: var(--ok-soft);
		color: var(--ok);
	}
	.cell b {
		font-size: var(--fs-lg, 1.1rem);
	}
	.l {
		font-size: var(--fs-xs);
		color: var(--muted);
	}
	.cell.good .l {
		color: inherit;
	}
	.ok {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin: 0;
		font-weight: 700;
		color: var(--ok);
	}
</style>
