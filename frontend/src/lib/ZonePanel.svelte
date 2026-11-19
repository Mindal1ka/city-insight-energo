<script lang="ts">
	// Бічна картка зони: якір, суми, «Можна поділитися», учасники (донори першими).
	import { kwh, uah, kText, type KClass } from './api-ses.ts';
	import type { Zone, ZoneMember } from './api-v2.ts';
	import KBadge from './KBadge.svelte';
	import { ZONE_COLORS, ZONE_LABELS } from './zone-meta.ts';

	let { zone, onclose }: { zone: Zone; onclose: () => void } = $props();

	const ORDER = { donor: 0, taker: 1, neutral: 2 } as const;
	const members = $derived(
		[...zone.members].sort(
			(a, b) => ORDER[a.role ?? 'neutral'] - ORDER[b.role ?? 'neutral'] || (b.surplus_kwh ?? 0) - (a.surplus_kwh ?? 0)
		)
	);
	const color = $derived(ZONE_COLORS[zone.status ?? 'no_ses']);
	const share = $derived(zone.shareable_kwh ?? 0);

	const ROLE: Record<string, { i: string; t: string; c: string }> = {
		donor: { i: '↑', t: 'віддає', c: '#1f6fd1' },
		taker: { i: '↓', t: 'бере', c: '#d9680f' },
		neutral: { i: '○', t: 'нейтральний', c: '#7a8594' }
	};
	const role = (m: ZoneMember) => ROLE[m.role ?? 'neutral'];
	function num(m: ZoneMember): string {
		if (m.role === 'donor') return `+${kwh(m.surplus_kwh)}`;
		if (m.role === 'taker') return `−${kwh(m.grid_kwh)}`;
		return kwh(m.cons_kwh);
	}
</script>

<section class="zp" aria-labelledby="zp-title" style="--c: {color}">
	<button type="button" class="x" onclick={onclose} aria-label="Закрити картку зони">✕</button>
	<div class="hd">
		<span class="st" title={zone.status ? ZONE_LABELS[zone.status] : ''}>{zone.status ? ZONE_LABELS[zone.status] : '—'}</span>
		<span class="cnt">{zone.count} · ☀ {zone.with_ses ?? 0}{#if zone.k != null} · K {kText(zone.k)}{/if}</span>
	</div>
	<h2 id="zp-title">{zone.name}</h2>

	<dl class="nums">
		<div><dt>Спожито</dt><dd>{kwh(zone.cons_kwh)}</dd></div>
		<div><dt>Згенеровано</dt><dd>{kwh(zone.gen_kwh)}</dd></div>
		<div><dt>Надлишок</dt><dd class="up">{kwh(zone.surplus_kwh)}</dd></div>
		<div><dt>З мережі</dt><dd class="dn">{kwh(zone.grid_kwh)}</dd></div>
	</dl>

	{#if share > 0}
		<div class="share">
			<span>Можна поділитися</span>
			<b>{kwh(share)}{#if zone.shareable_uah != null}<small> (≈ {uah(zone.shareable_uah)})</small>{/if}</b>
		</div>
	{/if}

	<ul class="mem">
		{#each members as m (m.id)}
			{@const r = role(m)}
			<li>
				<span class="ri" style="--r: {r.c}" title={r.t} role="img" aria-label={r.t}>{r.i}</span>
				<a href="/object/{m.id}" class="nm">{m.name}</a>
				{#if m.k_class}<KBadge cls={m.k_class as KClass} size="sm" showWord={false} showK={false} />{/if}
				<span class="v" style="color: {r.c}">{num(m)}</span>
			</li>
		{/each}
	</ul>
	<a class="open" href="/object/{zone.id}">Детальніше <span aria-hidden="true">→</span></a>
</section>

<style>
	.zp {
		position: absolute;
		z-index: 700;
		right: 58px;
		bottom: 22px;
		width: 340px;
		max-height: calc(100% - 200px);
		overflow-y: auto;
		padding: 16px 16px 14px;
		border-radius: 16px;
		background: rgba(255, 255, 255, 0.96);
		-webkit-backdrop-filter: saturate(1.5) blur(12px);
		backdrop-filter: saturate(1.5) blur(12px);
		box-shadow: 0 2px 6px rgba(15, 35, 65, 0.08), 0 12px 32px -14px rgba(15, 35, 65, 0.35);
		border-top: 4px solid var(--c);
	}
	.x {
		position: absolute;
		top: 10px;
		right: 10px;
		width: 30px;
		height: 30px;
		border: 0;
		border-radius: 50%;
		background: #eef2f7;
		color: #36425a;
		cursor: pointer;
		font-size: 0.8rem;
	}
	.x:hover {
		background: #e1e7ef;
	}
	.hd {
		display: flex;
		align-items: center;
		gap: 8px;
		font-size: 0.78rem;
		font-weight: 600;
		color: #4f5b6b;
	}
	.st {
		padding: 2px 10px;
		border-radius: 999px;
		background: var(--c);
		color: #fff;
		font-weight: 700;
	}
	.cnt {
		font-variant-numeric: tabular-nums;
	}
	h2 {
		margin: 6px 36px 10px 0;
		font-size: 1.02rem;
		line-height: 1.3;
		color: #0f1b2d;
	}
	.nums {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 6px;
		margin: 0;
	}
	.nums div {
		background: #f3f6fa;
		border-radius: 10px;
		padding: 7px 8px;
	}
	.nums dt {
		font-size: 0.66rem;
		color: #4f5b6b;
		font-weight: 600;
	}
	.nums dd {
		margin: 2px 0 0;
		font-weight: 800;
		font-size: 0.88rem;
		color: #0f1b2d;
		font-variant-numeric: tabular-nums;
	}
	.nums .up {
		color: #1f6fd1;
	}
	.nums .dn {
		color: #d9680f;
	}
	.share {
		margin-top: 8px;
		padding: 10px 12px;
		border-radius: 12px;
		background: #e3eefb;
		color: #0b3f7a;
		display: flex;
		flex-direction: column;
		gap: 2px;
		font-size: 0.74rem;
		font-weight: 600;
	}
	.share b {
		font-size: 1.25rem;
		font-weight: 800;
		font-variant-numeric: tabular-nums;
		color: #0b5cad;
	}
	.share small {
		font-size: 0.78rem;
		font-weight: 600;
		color: #36425a;
	}
	.mem {
		list-style: none;
		margin: 10px 0;
		padding: 0;
		display: grid;
		gap: 2px;
		max-height: 220px;
		overflow-y: auto;
	}
	.mem li {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 4px 2px;
		font-size: 0.8rem;
	}
	.ri {
		flex: none;
		display: grid;
		place-items: center;
		width: 20px;
		height: 20px;
		border-radius: 50%;
		background: var(--r);
		color: #fff;
		font-size: 0.72rem;
		font-weight: 800;
	}
	.nm {
		flex: 1;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		color: #0f1b2d;
		font-weight: 600;
		text-decoration: none;
	}
	.nm:hover {
		text-decoration: underline;
	}
	.v {
		flex: none;
		font-weight: 700;
		font-variant-numeric: tabular-nums;
		font-size: 0.76rem;
	}
	.open {
		display: flex;
		justify-content: center;
		gap: 6px;
		padding: 10px;
		border-radius: 12px;
		background: #0b5cad;
		color: #fff;
		font-weight: 700;
		text-decoration: none;
	}
	.open:hover {
		background: #084684;
	}
	a:focus-visible,
	button:focus-visible {
		outline: 3px solid var(--focus, #ffbf47);
		outline-offset: 2px;
	}
	@media (max-width: 700px) {
		.zp {
			left: 8px;
			right: 8px;
			bottom: 8px;
			width: auto;
			max-height: 55%;
			border-radius: 18px;
		}
	}
</style>
