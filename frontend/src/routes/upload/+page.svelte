<script lang="ts">
	// Сторінка «Оновити дані»: перетягніть XLSX з UMUNI — і все перерахується автоматично.
	// Стани: порожньо → файл вибрано → завантаження → готово / помилка (кожен зі своєю анімацією).
	import { api, errMessage, type UploadResult } from '#lib/api.ts';
	import { num, pct, dateTime, fileSize, plural } from '#lib/format.ts';
	import Term from '#lib/Term.svelte';
	import StatCard from '#lib/StatCard.svelte';
	import Icon from '#lib/Icon.svelte';
	import { fadeUp, scaleIn, reveal, revealKids } from '#lib/motion.ts';
	import Disclosure from '#lib/Disclosure.svelte';
	import DataStatus from '#lib/DataStatus.svelte';
	import { auth } from '#lib/auth.svelte.ts';
	import { canUpload, isInternal } from '#lib/roles.ts';

	const allowed = $derived(canUpload(auth.user));

	type Phase = 'idle' | 'selected' | 'uploading' | 'done' | 'error';

	let phase = $state<Phase>('idle');
	let file = $state<File | null>(null);
	let result = $state<UploadResult | null>(null);
	let error = $state<string | null>(null);
	let dragging = $state(false);
	let dragDepth = 0;
	let input = $state<HTMLInputElement>();
	let startBtn = $state<HTMLButtonElement>();
	let statusEl = $state<HTMLElement>();
	let version = $state(0); // після кожної спроби — перечитати свіжість і журнал

	function isXlsx(f: File): boolean {
		return f.name.toLowerCase().endsWith('.xlsx');
	}

	function choose(f: File | null | undefined) {
		result = null;
		error = null;
		if (!f) return;
		file = f;
		if (!isXlsx(f)) {
			error = `«${f.name}» — це не файл XLSX. Потрібне вивантаження з UMUNI у форматі Excel (.xlsx), збережене без змін.`;
			phase = 'error';
			return;
		}
		phase = 'selected';
		// Переводимо фокус на головну дію, щоб з клавіатури було одне натискання Enter
		queueMicrotask(() => startBtn?.focus());
	}

	function pick(e: Event) {
		const el = e.currentTarget as HTMLInputElement;
		choose(el.files?.[0]);
		el.value = ''; // дозволяє вибрати той самий файл ще раз
	}

	function onDragEnter(e: DragEvent) {
		if (!e.dataTransfer?.types.includes('Files')) return;
		e.preventDefault();
		dragDepth++;
		dragging = true;
	}
	function onDragOver(e: DragEvent) {
		if (!e.dataTransfer?.types.includes('Files')) return;
		e.preventDefault();
		e.dataTransfer.dropEffect = 'copy';
	}
	function onDragLeave() {
		dragDepth = Math.max(0, dragDepth - 1);
		if (!dragDepth) dragging = false;
	}
	function onDrop(e: DragEvent) {
		e.preventDefault();
		dragDepth = 0;
		dragging = false;
		if (phase === 'uploading') return;
		choose(e.dataTransfer?.files?.[0]);
	}

	async function send() {
		if (!file || !isXlsx(file)) return;
		phase = 'uploading';
		error = null;
		result = null;
		try {
			result = await api.upload(file);
			phase = 'done';
		} catch (err) {
			error = errMessage(err);
			phase = 'error';
		}
		version++;
		queueMicrotask(() => statusEl?.focus());
	}

	function again() {
		file = null;
		result = null;
		error = null;
		phase = 'idle';
		queueMicrotask(() => input?.click());
	}

	function kindLabel(kind: string): string {
		if (kind === 'buildings') return 'характеристики будівель (реєстр)';
		if (kind === 'annual') return 'річний звіт про використання ресурсів';
		return kind;
	}
</script>

<svelte:head><title>Оновити дані · Insight Tool</title></svelte:head>

<div class="page-head">
	<div>
		<h1>Оновити дані <Term key="UMUNI" plain /></h1>
	</div>
</div>

{#if !allowed}
	<!-- Завантаження — лише провідний фахівець з енергозабезпечення і адміністратор даних -->
	<section class="card lock" aria-labelledby="lock-h" use:reveal={1}>
		<span class="lock-ic" aria-hidden="true"><Icon name="lock" size={26} /></span>
		<h2 id="lock-h">{auth.user && isInternal(auth.user) ? 'Лише для провідного фахівця з енергозабезпечення' : 'Доступно після входу'}</h2>
		{#if !(auth.user && isInternal(auth.user))}
			<a class="btn" href="/login?next={encodeURIComponent('/upload')}">Увійти <Icon name="arrow-right" size={18} /></a>
		{/if}
	</section>
{:else}
<div class="layout" use:revealKids={{ delay: 40, step: 40 }}>
	<section class="card up" aria-labelledby="up-h">
		<h2 id="up-h" class="visually-hidden">Завантаження файлу</h2>

		<input
			bind:this={input}
			id="file"
			class="visually-hidden"
			type="file"
			accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
			onchange={pick}
			disabled={phase === 'uploading'}
			aria-describedby="file-help"
		/>

		{#if phase === 'idle' || phase === 'selected' || phase === 'error'}
			<div
				class="drop"
				class:dragging
				class:has-file={phase === 'selected'}
				class:bad={phase === 'error'}
				role="presentation"
				ondragenter={onDragEnter}
				ondragover={onDragOver}
				ondragleave={onDragLeave}
				ondrop={onDrop}
			>
				{#if phase === 'selected' && file}
					<div class="picked" in:scaleIn>
						<span class="file-ico" aria-hidden="true">
							<svg viewBox="0 0 32 32" width="40" height="40"
								><path d="M8 3h11l7 7v17a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z" fill="#e3f4e8" stroke="#1a7f37" stroke-width="1.6" /><path d="M19 3v7h7" fill="none" stroke="#1a7f37" stroke-width="1.6" /><path d="m11 15 6 8m0-8-6 8" stroke="#1a7f37" stroke-width="2" stroke-linecap="round" /></svg
							>
						</span>
						<span class="picked-txt">
							<span class="step-l">Файл вибрано</span>
							<strong class="fname">{file.name}</strong>
							<span class="muted small">{fileSize(file.size)}</span>
						</span>
						<div class="picked-actions">
							<button bind:this={startBtn} type="button" class="btn btn-lg go" onclick={send}>
								<Icon name="arrow-right" size={18} /> Завантажити й перерахувати
							</button>
							<button type="button" class="btn btn-secondary" onclick={() => input?.click()}>Обрати інший</button>
						</div>
					</div>
				{:else}
					<label for="file" class="drop-label">
						<span class="cloud" aria-hidden="true">
							<svg viewBox="0 0 48 48" width="56" height="56"
								><path d="M14 36h-1.5a9 9 0 0 1-1-17.95A12 12 0 0 1 35 15.2 8.5 8.5 0 0 1 36 36h-2" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" /><path class="arrow" d="M24 40V24m-6 6 6-6 6 6" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" /></svg
							>
						</span>
						<span class="drop-title">
							{dragging ? 'Відпустіть файл тут' : 'Перетягніть файл XLSX сюди'}
						</span>
						<span class="muted drop-or">або <span class="fake-link">оберіть його на комп’ютері</span></span>
						<span class="pick-btn">
							<svg viewBox="0 0 24 24" width="22" height="22"
								><path d="M12 16V4m-5 5 5-5 5 5M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" /></svg
							>
							Обрати файл
						</span>
						<span class="muted small pick-sub">Excel (.xlsx) з UMUNI</span>
					</label>
				{/if}
			</div>
		{/if}

		<div class="status" aria-live="polite" bind:this={statusEl} tabindex="-1">
			{#if phase === 'uploading'}
				<div class="busy" in:fadeUp>
					<p class="busy-t"><strong>Завантажуємо й перераховуємо…</strong></p>
					<p class="muted small">{file?.name}</p>
					<span class="bar" aria-hidden="true"><span></span></span>
				</div>
			{:else if phase === 'error' && error}
				<div class="res res-bad" role="alert" in:fadeUp>
					<span class="res-ico bad-ico" aria-hidden="true">
						<svg viewBox="0 0 24 24" width="26" height="26"><path d="m7 7 10 10M17 7 7 17" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" /></svg>
					</span>
					<div>
						<p><strong>Файл не прийнято.</strong> {error}</p>
						<div class="res-actions">
							{#if file && isXlsx(file)}
								<button type="button" class="btn" onclick={send}>Спробувати ще раз</button>
							{/if}
							<button type="button" class="btn btn-secondary" onclick={() => input?.click()}>Обрати інший файл</button>
						</div>
					</div>
				</div>
			{:else if phase === 'done' && result}
				<div class="done" in:fadeUp>
					<div class="res res-ok">
						<span class="res-ico ok-ico" aria-hidden="true">
							<svg viewBox="0 0 24 24" width="28" height="28"><path class="tick" d="m5.5 12.5 4.2 4.2 8.8-9.4" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" /></svg>
						</span>
						<div>
							<p class="done-t"><strong>Готово! Дані оновлено.</strong></p>
							<p class="muted">{kindLabel(result.kind)}</p>
						</div>
					</div>
					<div class="done-stats">
						<div>
							<StatCard label="Будівель у базі" value={result.summary.buildings} icon="building" hint="Усі будівлі з реєстру." />
						</div>
						<div>
							<StatCard
								label="У рейтингу"
								value={result.summary.in_rating}
								icon="gauge"
								href="/rating"
								hint="Мають повні дані для порівняння."
							/>
						</div>
						<div>
							<StatCard
								label="Проблем у даних"
								value={result.summary.defects}
								icon="alert"
								tone={result.summary.defects ? 'warn' : 'good'}
								hint="На {num(result.summary.defect_buildings)} {plural(result.summary.defect_buildings, ['будівлі', 'будівлях', 'будівлях'])}."
							/>
						</div>
					</div>
					<ul class="years small muted">
						{#each Object.entries(result.summary.years) as [y, s] (y)}
							<li>
								{y} рік: вивантаження від {dateTime(s.created)}{s.partial ? ` — неповний рік (≈ ${pct(s.coverage)})` : ''}
							</li>
						{/each}
					</ul>
					<div class="res-actions">
						<a class="btn" href="/overview">Переглянути споживання</a>
						<button type="button" class="btn btn-secondary" onclick={again}>Завантажити ще один файл</button>
					</div>
				</div>
			{/if}
		</div>
	</section>

	<aside class="card how" aria-label="Як це працює">
		<ol class="steps">
			<li><span class="n" aria-hidden="true">1</span><span><strong>XLSX з UMUNI</strong></span></li>
			<li><span class="n" aria-hidden="true">2</span><span><strong><span class="hide-phone">Перетягніть сюди</span><span class="only-phone">Оберіть тут</span></strong></span></li>
			<li><span class="n" aria-hidden="true">3</span><span><strong>Усе перераховано</strong></span></li>
		</ol>
		<Disclosure summary="Як рахуємо">
			<p id="file-help" class="muted small">
				Підходять «Характеристики будівель» (Buildings_Info_Report) і «Річне використання ресурсів» за будь-який рік — файл як є, без змін.
				Тип звіту й рік визначаються автоматично. Якщо за рік уже є файл, береться новіший; неповний поточний рік позначається окремо.
			</p>
		</Disclosure>
	</aside>
</div>

<DataStatus {version} />
{/if}

<style>
	.lock {
		display: grid;
		justify-items: center;
		gap: 0.9rem;
		max-width: 26rem;
		margin: 2rem auto;
		text-align: center;
	}
	.lock h2 {
		margin: 0;
		font-size: 1.35rem;
	}
	.lock-ic {
		display: grid;
		place-items: center;
		width: 3.25rem;
		height: 3.25rem;
		border-radius: 50%;
		background: var(--accent-soft);
		color: var(--accent);
	}
	.layout {
		display: grid;
		grid-template-columns: minmax(0, 1.6fr) minmax(0, 1fr);
		gap: 1.25rem;
		align-items: start;
	}
	@media (max-width: 900px) {
		.layout {
			grid-template-columns: 1fr;
		}
	}
	.up {
		margin: 0;
	}
	.how {
		margin: 0;
	}
	.drop {
		position: relative;
		border: 2px dashed var(--line-strong);
		border-radius: var(--radius-lg);
		background: #fafbfd;
		transition:
			border-color 0.2s,
			background 0.2s,
			transform 0.25s var(--ease),
			box-shadow 0.25s;
	}
	.drop:has(.drop-label:hover) {
		border-color: var(--accent);
		background: var(--accent-soft);
	}
	:global(#file:focus-visible) + .drop {
		outline: 3px solid var(--focus);
		outline-offset: 3px;
	}
	.drop.dragging {
		border-color: var(--accent);
		border-style: solid;
		background: var(--accent-soft);
		transform: scale(1.015);
		box-shadow: 0 0 0 6px color-mix(in srgb, var(--accent) 15%, transparent);
	}
	.drop.has-file {
		border-style: solid;
		border-color: var(--ok);
		background: var(--ok-soft);
	}
	.drop.bad {
		border-color: var(--bad);
	}
	.drop-label {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.4rem;
		padding: 2.75rem 1.5rem;
		text-align: center;
		cursor: pointer;
		font-weight: 400;
		font-size: 1rem;
	}
	.cloud {
		color: var(--accent);
		margin-bottom: 0.25rem;
	}
	.drop-title {
		font-size: 1.2rem;
		font-weight: 650;
	}
	.fake-link {
		color: var(--accent);
		text-decoration: underline;
		font-weight: 600;
	}
	@media (prefers-reduced-motion: no-preference) {
		.cloud .arrow {
			animation: bob 2.2s var(--ease) infinite;
		}
		.dragging .cloud .arrow {
			animation-duration: 0.9s;
		}
		@keyframes bob {
			0%,
			100% {
				transform: translateY(0);
			}
			50% {
				transform: translateY(-3px);
			}
		}
	}
	.picked {
		display: grid;
		grid-template-columns: auto minmax(0, 1fr);
		gap: 0.75rem 1rem;
		align-items: center;
		padding: 1.25rem 1.25rem;
	}
	.picked-txt {
		display: flex;
		flex-direction: column;
		min-width: 0;
	}
	.step-l {
		font-size: 0.85rem;
		font-weight: 600;
		color: var(--ok);
	}
	.fname {
		font-size: 1.05rem;
		overflow-wrap: anywhere;
	}
	.picked-actions {
		grid-column: 1 / -1;
		display: flex;
		flex-wrap: wrap;
		gap: 0.6rem;
	}
	.go {
		min-height: 46px;
		padding: 0.6rem 1.25rem;
	}
	.status:focus,
	.status:focus-visible {
		outline: none;
		box-shadow: none;
	}
	.busy {
		padding: 1.5rem 0.25rem 0.5rem;
	}
	.busy p {
		margin: 0 0 0.3rem;
	}
	.busy-t {
		font-size: 1.1rem;
	}
	.bar {
		display: block;
		position: relative;
		height: 8px;
		margin-top: 0.75rem;
		border-radius: var(--r-sm);
		background: var(--neutral-soft);
		overflow: hidden;
	}
	.bar span {
		position: absolute;
		inset: 0;
		width: 40%;
		border-radius: var(--r-sm);
		background: linear-gradient(90deg, var(--accent), var(--sun));
	}
	@media (prefers-reduced-motion: no-preference) {
		.bar span {
			animation: slide 1.3s var(--ease) infinite;
		}
		@keyframes slide {
			from {
				transform: translateX(-100%);
			}
			to {
				transform: translateX(260%);
			}
		}
	}
	@media (prefers-reduced-motion: reduce) {
		.bar span {
			width: 100%;
			opacity: 0.6;
		}
	}
	.res {
		display: grid;
		grid-template-columns: auto minmax(0, 1fr);
		gap: 0.9rem;
		align-items: start;
		margin-top: 1rem;
		padding: 1rem 1.1rem;
		border-radius: var(--radius);
		border: 1px solid;
	}
	.res p {
		margin: 0 0 0.4rem;
	}
	.res-bad {
		background: var(--bad-soft);
		border-color: var(--bad);
	}
	.res-ok {
		background: var(--ok-soft);
		border-color: var(--ok);
	}
	.res-ico {
		display: grid;
		place-items: center;
		width: 2.75rem;
		height: 2.75rem;
		border-radius: 50%;
		color: #fff;
	}
	.bad-ico {
		background: var(--bad);
	}
	.ok-ico {
		background: var(--ok);
	}
	.done-t {
		font-size: 1.15rem;
	}
	@media (prefers-reduced-motion: no-preference) {
		.res-bad {
			animation: shake 0.42s var(--ease);
		}
		@keyframes shake {
			20% {
				transform: translateX(-6px);
			}
			40% {
				transform: translateX(5px);
			}
			60% {
				transform: translateX(-3px);
			}
			80% {
				transform: translateX(2px);
			}
		}
		.ok-ico {
			animation: pop 0.45s cubic-bezier(0.34, 1.56, 0.64, 1) both;
		}
		@keyframes pop {
			from {
				transform: scale(0.4);
				opacity: 0;
			}
		}
		.tick {
			stroke-dasharray: 22;
			stroke-dashoffset: 22;
			animation: draw 0.45s var(--ease) 0.25s forwards;
		}
		@keyframes draw {
			to {
				stroke-dashoffset: 0;
			}
		}
	}
	.res-actions {
		display: flex;
		flex-wrap: wrap;
		gap: 0.6rem;
		margin-top: 0.75rem;
	}
	.done-stats {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, 12.5rem), 1fr));
		gap: 0.9rem;
		margin: 1rem 0 0.75rem;
	}
	.done-stats > div {
		display: grid;
	}
	.years {
		margin: 0 0 0.25rem;
		padding-left: 1.1rem;
	}
	.steps {
		list-style: none;
		margin: 0 0 1rem;
		padding: 0;
		display: grid;
		gap: 0.9rem;
	}
	.steps li {
		display: grid;
		grid-template-columns: 2.1rem minmax(0, 1fr);
		gap: 0.75rem;
		align-items: start;
	}
	.n {
		display: grid;
		place-items: center;
		width: 2.1rem;
		height: 2.1rem;
		border-radius: 50%;
		background: var(--sun-soft);
		color: var(--sun-ink);
		font-weight: 700;
	}
	@media (prefers-reduced-motion: reduce) {
		.drop {
			transition: none;
		}
		.drop.dragging {
			transform: none;
		}
	}
	/* Велика кнопка «Обрати файл» — лише на телефоні (перетягування там не працює) */
	.pick-btn,
	.pick-sub {
		display: none;
	}
	@media (max-width: 640px) {
		.drop:not(.has-file):not(.bad) {
			border: 0;
			background: none;
		}
		.drop.bad {
			border-style: solid;
			border-width: 1px;
		}
		.drop:has(.drop-label:hover) {
			background: none;
		}
		.drop-label {
			padding: 0.25rem 0;
			gap: 0.5rem;
		}
		.drop.bad .drop-label {
			padding: 0.75rem;
		}
		.cloud,
		.drop-title,
		.drop-or {
			display: none;
		}
		.pick-btn {
			display: flex;
			align-items: center;
			justify-content: center;
			gap: 0.6rem;
			width: 100%;
			min-height: 60px;
			padding: 0.9rem 1.25rem;
			border-radius: var(--r-btn);
			background: var(--accent);
			color: #fff;
			font-size: 1.125rem;
			font-weight: 700;
			box-shadow: 0 6px 18px color-mix(in srgb, var(--accent) 28%, transparent);
			transition: transform 0.15s;
		}
		.drop-label:active .pick-btn {
			transform: scale(0.98);
		}
		.pick-sub {
			display: block;
		}
		:global(#file:focus-visible) + .drop {
			outline: none;
		}
		:global(#file:focus-visible) + .drop .pick-btn {
			outline: 3px solid var(--focus);
			outline-offset: 3px;
		}
		.picked {
			padding: 1rem;
			gap: 0.6rem 0.75rem;
		}
		.picked-actions,
		.res-actions {
			flex-direction: column;
			align-items: stretch;
		}
		.picked-actions .btn,
		.res-actions .btn {
			width: 100%;
			justify-content: center;
		}
		.go {
			min-height: 52px;
		}
		.res {
			grid-template-columns: 1fr;
			gap: 0.6rem;
			padding: 0.9rem;
		}
		.done-stats {
			grid-template-columns: repeat(2, minmax(0, 1fr));
			gap: 0.625rem;
		}
		.done-stats > :last-child:nth-child(odd) {
			grid-column: 1 / -1;
		}
		.layout {
			gap: 0.875rem;
		}
	}
</style>
