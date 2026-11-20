<script lang="ts">
	// Бейдж «свіжість даних» у меню: колір за найгіршим джерелом, по кліку — список джерел.
	import { fresh, loadFreshness, STATUS_TEXT, STATUS_SHORT, ago } from './freshness.svelte.ts';
	import { date } from './format.ts';
	import { auth } from './auth.svelte.ts';
	import { canUpload } from './roles.ts';

	let open = $state(false);
	let root = $state<HTMLElement>();
	const id = `fresh-pop-${Math.random().toString(36).slice(2, 8)}`;

	$effect(() => {
		if (auth.user) loadFreshness();
	});

	const d = $derived(fresh.data);
	const status = $derived(d?.overall ?? null);
	const late = $derived(d ? d.sources.filter((s) => s.status !== 'fresh') : []);

	function outside(e: MouseEvent) {
		if (open && root && !root.contains(e.target as Node)) open = false;
	}
	function key(e: KeyboardEvent) {
		if (open && e.key === 'Escape') {
			open = false;
			(root?.querySelector('.badge') as HTMLElement | null)?.focus();
		}
	}
</script>

<svelte:window onclick={outside} onkeydown={key} />

{#if d || fresh.error}
	<div class="fwrap" bind:this={root}>
		<button
			type="button"
			class="badge {status ?? 'unknown'}"
			aria-expanded={open}
			aria-controls={id}
			onclick={() => (open = !open)}
		>
			<span class="dot" aria-hidden="true"></span>
			<span class="txt">
				{#if d && status}
					<strong>{STATUS_TEXT[status]}</strong>
					<span class="sub">
						{#if late.length}
							{late.length} {late.length === 1 ? 'джерело' : late.length < 5 ? 'джерела' : 'джерел'} — оновити
						{:else}
							UMUNI від {date(d.as_of)}
						{/if}
					</span>
				{:else}
					<strong>Свіжість невідома</strong>
					<span class="sub">сервер не відповів</span>
				{/if}
			</span>
		</button>

		{#if open && d}
			<div class="pop" {id} role="region" aria-label="Свіжість джерел даних">
				<p class="pop-t">Свіжість джерел</p>
				<ul>
					{#each d.sources as s (s.key)}
						<li>
							<span class="dot {s.status}" aria-hidden="true"></span>
							<span class="s-txt">
								<span class="s-l">{s.label}{#if s.demo}<span class="demo" title="Дата з ДЕМО-журналу завантажень"> · демо</span>{/if}</span>
								<span class="s-d">
									{#if s.kind === 'openbudget' || s.kind === 'spending'}
										{s.detail}
									{:else}
										{date(s.as_of)} · {ago(s.age_days)}
									{/if}
								</span>
							</span>
							<span class="s-st {s.status}">{STATUS_SHORT[s.status]}</span>
						</li>
					{/each}
				</ul>
				{#if canUpload(auth.user)}
					<a class="pop-a" href="/upload#freshness" onclick={() => (open = false)}>Оновити дані →</a>
				{/if}
			</div>
		{/if}
	</div>
{/if}

<style>
	.fwrap {
		position: relative;
		margin: 0.5rem 0 0.6rem;
	}
	.badge {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		width: 100%;
		padding: 0.5rem 0.65rem;
		border-radius: 10px;
		border: 1px solid var(--line);
		background: var(--surface, #fff);
		font: inherit;
		text-align: left;
		cursor: pointer;
		color: var(--ink);
		transition:
			border-color 0.15s,
			background 0.15s;
	}
	.badge:hover {
		border-color: var(--line-strong);
	}
	.badge.fresh {
		background: var(--ok-soft);
		border-color: color-mix(in srgb, var(--ok) 35%, transparent);
	}
	.badge.due {
		background: var(--warn-soft);
		border-color: color-mix(in srgb, var(--warn) 45%, transparent);
	}
	.badge.stale {
		background: var(--bad-soft);
		border-color: color-mix(in srgb, var(--bad) 45%, transparent);
	}
	.txt {
		display: flex;
		flex-direction: column;
		min-width: 0;
		line-height: 1.25;
	}
	.txt strong {
		font-size: 0.82rem;
	}
	.sub {
		font-size: 0.74rem;
		color: var(--muted);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.dot {
		flex: none;
		width: 9px;
		height: 9px;
		border-radius: 50%;
		background: var(--muted);
	}
	.badge.fresh .dot,
	.dot.fresh {
		background: var(--ok);
	}
	.badge.due .dot,
	.dot.due {
		background: var(--warn);
	}
	.badge.stale .dot,
	.dot.stale {
		background: var(--bad);
	}
	@media (prefers-reduced-motion: no-preference) {
		.badge.due .dot,
		.badge.stale .dot {
			animation: pulse 1.8s ease-in-out infinite;
		}
		@keyframes pulse {
			50% {
				opacity: 0.35;
			}
		}
	}
	.pop {
		position: absolute;
		left: 0;
		bottom: calc(100% + 0.4rem);
		z-index: 30;
		width: min(20rem, calc(100vw - 2rem));
		padding: 0.75rem 0.8rem 0.65rem;
		border-radius: 12px;
		border: 1px solid var(--line);
		background: #fff;
		box-shadow: 0 12px 32px rgb(15 23 42 / 0.16);
	}
	.pop-t {
		margin: 0 0 0.45rem;
		font-size: 0.78rem;
		font-weight: 700;
		color: var(--muted);
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}
	ul {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 0.45rem;
	}
	li {
		display: grid;
		grid-template-columns: auto minmax(0, 1fr) auto;
		gap: 0.5rem;
		align-items: center;
	}
	.s-txt {
		display: flex;
		flex-direction: column;
		min-width: 0;
		line-height: 1.25;
	}
	.s-l {
		font-size: 0.8rem;
		font-weight: 600;
	}
	.demo {
		font-weight: 500;
		color: var(--sun-ink);
	}
	.s-d {
		font-size: 0.74rem;
		color: var(--muted);
	}
	.s-st {
		font-size: 0.7rem;
		font-weight: 600;
		white-space: nowrap;
	}
	.s-st.fresh {
		color: var(--ok);
	}
	.s-st.due {
		color: var(--warn);
	}
	.s-st.stale {
		color: var(--bad);
	}
	.pop-a {
		display: inline-block;
		margin-top: 0.6rem;
		font-size: 0.82rem;
		font-weight: 600;
		color: var(--accent);
	}
</style>
