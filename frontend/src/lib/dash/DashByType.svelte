<!-- За типом закладу: середній K (зважений) на шкалі 0–2 + кількість об'єктів -->
<script lang="ts">
	import { CLASS_BY_ID, classOf, type TypeRow } from './DashData.ts';
	let {
		rows,
		low = 0.8,
		high = 1.2,
		showK = true,
		active = '',
		onpick
	}: {
		rows: TypeRow[];
		low?: number;
		high?: number;
		showK?: boolean;
		active?: string;
		onpick?: (key: string) => void;
	} = $props();

	const XMAX = 2;
	const pos = (v: number) => `${(Math.min(v, XMAX) / XMAX) * 100}%`;
	const maxCount = $derived(Math.max(1, ...rows.map((r) => r.count)));
	const fmtK = (k: number) => k.toLocaleString('uk-UA', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
</script>

<ul class="bt" aria-label="За типом закладу">
	{#each rows as r (r.key)}
		{@const cls = showK ? classOf(r.k, r.withSes > 0, { low, high } as never) : null}
		{@const meta = cls ? CLASS_BY_ID[cls] : null}
		<li>
			<button
				type="button"
				class="row"
				aria-pressed={active === r.key}
				disabled={!onpick}
				onclick={() => onpick?.(active === r.key ? '' : r.key)}
			>
				<span class="lbl">{r.label}</span>
				<span class="cnt"><b>{r.count}</b>{#if showK}<span class="ses"> · СЕС {r.withSes}</span>{/if}</span>
				{#if showK}
					<span class="track" aria-hidden="true">
						<span class="zone" style="left:{pos(low)};width:calc({pos(high)} - {pos(low)})"></span>
						<span class="one" style="left:{pos(1)}"></span>
						{#if r.k !== null && meta}
							<span class="bar" style="width:{pos(r.k)};background:{meta.color}"></span>
						{/if}
					</span>
					<span class="k" style={meta ? `color:${meta.ink}` : ''}>
						{#if r.k !== null && meta}<span aria-hidden="true">{meta.sym}</span> {fmtK(r.k)}<span class="visually-hidden"> ({meta.short})</span>{:else}—{/if}
					</span>
				{:else}
					<span class="track" aria-hidden="true">
						<span class="bar cnt-bar" style="width:{(r.count / maxCount) * 100}%"></span>
					</span>
					<span class="k"></span>
				{/if}
			</button>
		</li>
	{/each}
</ul>
{#if showK}
	<div class="scale" aria-hidden="true">
		<span style="left:0;transform:none">0</span><span style="left:{pos(low)}">{fmtK(low).replace(/0$/, '')}</span><span style="left:{pos(1)}">1</span><span
			style="left:{pos(high)}">{fmtK(high).replace(/0$/, '')}</span
		><span style="left:100%;transform:translateX(-100%)">2 K</span>
	</div>
{/if}

<style>
	.bt {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 0.2rem;
	}
	.row {
		display: grid;
		grid-template-columns: minmax(0, 1fr) auto 4rem;
		grid-template-areas: 'lbl cnt k' 'trk trk trk';
		align-items: center;
		gap: 0.3rem 0.75rem;
		width: 100%;
		padding: 0.4rem 0.5rem;
		border: 1px solid transparent;
		border-radius: var(--r-btn);
		background: none;
		font: inherit;
		color: var(--text);
		text-align: left;
		cursor: pointer;
	}
	.lbl {
		grid-area: lbl;
	}
	.cnt {
		grid-area: cnt;
	}
	.k {
		grid-area: k;
	}
	.track {
		grid-area: trk;
	}
	.row:disabled {
		cursor: default;
	}
	.row:not(:disabled):hover {
		background: var(--neutral-soft);
	}
	.row[aria-pressed='true'] {
		border-color: var(--navy);
		background: var(--accent-soft);
	}
	.lbl {
		font-weight: 600;
		font-size: 0.92rem;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.cnt {
		font-variant-numeric: tabular-nums;
		font-size: 0.85rem;
		color: var(--muted);
		white-space: nowrap;
	}
	.cnt b {
		color: var(--ink);
		font-size: 0.95rem;
	}
	.track {
		position: relative;
		height: 12px;
		border-radius: var(--r-input);
		background: var(--line-soft);
		overflow: hidden;
	}
	.zone {
		position: absolute;
		top: 0;
		bottom: 0;
		background: #cfe9d6;
	}
	.one {
		position: absolute;
		top: 0;
		bottom: 0;
		width: 2px;
		margin-left: -1px;
		background: var(--ink);
		opacity: 0.35;
		z-index: 2;
	}
	.bar {
		position: absolute;
		left: 0;
		top: 3px;
		bottom: 3px;
		border-radius: var(--r-sm);
		/* Смуги ростуть від нуля лише при першому показі (transform), ширина — без анімації */
		animation: grow var(--dur-slow) var(--ease-emph);
		transform-origin: left;
		z-index: 1;
	}
	.cnt-bar {
		background: var(--cons);
	}
	@keyframes grow {
		from {
			transform: scaleX(0);
		}
	}
	.k {
		font-weight: 800;
		font-variant-numeric: tabular-nums;
		text-align: right;
		white-space: nowrap;
	}
	.scale {
		position: relative;
		height: 1rem;
		margin: 0.15rem calc(0.5rem + 1px) 0;
		font-size: 11px;
		color: var(--muted);
	}
	.scale span {
		position: absolute;
		transform: translateX(-50%);
		white-space: nowrap;
	}
	@media (prefers-reduced-motion: reduce) {
		.bar {
			transition: none;
			animation: none;
		}
	}
</style>
