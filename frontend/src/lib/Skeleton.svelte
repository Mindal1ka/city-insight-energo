<script lang="ts">
	// Каркас сторінки, поки вантажаться дані: сірі «заготовки» замість стрибків макета.
	// Готові макети:  <Skeleton variant="kpis" count={4} />, <Skeleton variant="table" rows={8} />, <Skeleton variant="text" rows={3} />
	// Примітиви (резервують ТОЧНИЙ розмір слота, куди потім стане вміст — тож поява не зсуває макет):
	//   <Skeleton variant="line" w="60%" />            рядок тексту (h типово 0.85rem)
	//   <Skeleton variant="block" h="16rem" />         графік / мапа / таблиця
	//   <Skeleton variant="tile" h="7.5rem" />         плитка KPI з рамкою картки
	// Мерехтіння повільне (1.4 с) і вимикається при prefers-reduced-motion (див. .skeleton в app.css).
	let {
		variant = 'table',
		rows = 6,
		count = 4,
		w,
		h,
		label = 'Завантаження даних…'
	}: {
		variant?: 'kpis' | 'table' | 'text' | 'cards' | 'page' | 'line' | 'block' | 'tile';
		rows?: number;
		count?: number;
		w?: string;
		h?: string;
		label?: string;
	} = $props();

	// Вміст, що заміняє каркас, з'являється з рухом навіть після довгого завантаження (motion.ts → inFirstWave)
	import { onDestroy } from 'svelte';
	import { skeletonMounted } from './motion.ts';
	onDestroy(skeletonMounted());
</script>

{#if variant === 'line' || variant === 'block'}
	<span
		class="skeleton sk-prim"
		class:sk-l={variant === 'line'}
		style:width={w ?? (variant === 'line' ? '60%' : '100%')}
		style:height={h ?? (variant === 'line' ? '0.85rem' : '12rem')}
		aria-hidden="true"
	></span>
{:else if variant === 'tile'}
	<div class="sk-kpi sk-tile" style:min-height={h ?? '7.5rem'} style:width={w} aria-hidden="true">
		<span class="skeleton sk-line" style="width:55%"></span>
		<span class="skeleton sk-big"></span>
		<span class="skeleton sk-line" style="width:75%"></span>
	</div>
{:else}

<div class="sk-root" role="status" aria-live="polite">
	<span class="visually-hidden">{label}</span>
	<div aria-hidden="true">
		{#if variant === 'kpis' || variant === 'page'}
			<div class="sk-kpis">
				{#each { length: count } as _, i (i)}
					<div class="sk-kpi">
						<span class="skeleton sk-line" style="width:55%"></span>
						<span class="skeleton sk-big"></span>
						<span class="skeleton sk-line" style="width:75%"></span>
					</div>
				{/each}
			</div>
		{/if}
		{#if variant === 'cards'}
			<div class="sk-cards">
				{#each { length: count } as _, i (i)}
					<div class="sk-card">
						<span class="skeleton sk-line" style="width:70%"></span>
						<span class="skeleton sk-line" style="width:45%"></span>
						<span class="skeleton sk-block"></span>
					</div>
				{/each}
			</div>
		{/if}
		{#if variant === 'table' || variant === 'page'}
			<div class="sk-table">
				<span class="skeleton sk-head"></span>
				{#each { length: rows } as _, i (i)}
					<div class="sk-row">
						<span class="skeleton sk-line" style="width:{40 + ((i * 37) % 45)}%"></span>
						<span class="skeleton sk-line sk-num"></span>
						<span class="skeleton sk-line sk-num"></span>
					</div>
				{/each}
			</div>
		{/if}
		{#if variant === 'text'}
			<div class="sk-text">
				{#each { length: rows } as _, i (i)}
					<span class="skeleton sk-line" style="width:{i === rows - 1 ? 60 : 95 - ((i * 13) % 20)}%"></span>
				{/each}
			</div>
		{/if}
	</div>
</div>
{/if}

<style>
	.sk-prim {
		display: block;
	}
	.sk-prim.sk-l {
		display: inline-block;
		vertical-align: middle;
	}
	.sk-tile {
		min-height: auto;
	}
	.sk-root {
		margin-bottom: 1.25rem;
	}
	.sk-kpis,
	.sk-cards {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(min(100%, 15.5rem), 1fr));
		gap: 1rem;
		margin-bottom: 1.25rem;
	}
	.sk-kpi,
	.sk-card {
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
		padding: 1.15rem 1.25rem 1.2rem;
		background: var(--surface);
		border: 1px solid var(--card-line);
		border-radius: var(--radius-lg);
		box-shadow: var(--shadow);
	}
	.sk-kpi {
		min-height: 9.5rem;
	}
	.sk-card {
		min-height: 11rem;
	}
	.sk-line {
		display: block;
		height: 0.85rem;
	}
	.sk-big {
		display: block;
		height: 2.2rem;
		width: 65%;
	}
	.sk-block {
		display: block;
		flex: 1;
		min-height: 5rem;
	}
	.sk-table {
		background: var(--surface);
		border: 1px solid var(--card-line);
		border-radius: var(--radius-lg);
		box-shadow: var(--shadow);
		overflow: hidden;
	}
	.sk-head {
		display: block;
		height: 2.6rem;
		border-radius: 0;
	}
	.sk-row {
		display: grid;
		grid-template-columns: 1fr 6rem 6rem;
		gap: 1.5rem;
		align-items: center;
		padding: 0.85rem 1rem;
		border-top: 1px solid #edf0f4;
	}
	.sk-num {
		width: 100%;
	}
	.sk-text {
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
	}
</style>
