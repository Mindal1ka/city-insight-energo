<script lang="ts" module>
	export interface PaletteLink {
		href: string;
		label: string;
		hint?: string;
	}

	/** Сторінки, на які можна перейти з пошуку (only — лише для службових ролей) */
	export const PALETTE_PAGES: (PaletteLink & { only?: 'internal' | 'upload' })[] = [
		{ href: '/', label: 'Мапа', hint: 'Об’єкти на карті, клас СЕС' },
		{ href: '/dashboard', label: 'Огляд', hint: 'Головні цифри громади' },
		{ href: '/objects', label: 'Об’єкти', hint: 'Список, фільтри' },
		{ href: '/energy', label: 'Розподіл енергії', hint: 'Генерація, споживання, надлишок' },
		{ href: '/network', label: 'Баланс мережі', hint: 'Навантаження та покриття СЕС' },
		{ href: '/finance', label: 'Фінанси', hint: 'Витрати за розпорядниками' },
		{ href: '/report', label: 'Звіт', hint: 'Підсумок по електроенергії' },
		{ href: '/overview', label: 'Споживання', hint: 'Електроенергія громади' },
		{ href: '/rating', label: 'Рейтинг', hint: 'кВт·год/м²' },
		{ href: '/upload', label: 'Оновити дані', hint: 'Завантажити UMUNI', only: 'upload' }
	];
</script>

<script lang="ts">
	// Глобальний пошук (Ctrl+K): будівлі за назвою чи адресою + швидкі переходи на сторінки.
	// Шаблон «комбобокс + список» у модальному <dialog>: стрілки, Enter, Esc, Home/End.
	import { goto } from '$app/navigation';
	import { tick } from 'svelte';
	import { api, errMessage, type Building } from './api.ts';
	import Icon from './Icon.svelte';
	import { catLabel } from './categories.ts';
	import { auth } from './auth.svelte.ts';
	import { isInternal, canUpload } from './roles.ts';

	let { open = $bindable(false) }: { open?: boolean } = $props();

	let dialog = $state<HTMLDialogElement>();
	let input = $state<HTMLInputElement>();
	let listEl = $state<HTMLUListElement>();
	let query = $state('');
	let active = $state(0);
	let buildings = $state<Building[] | null>(null);
	let loadError = $state<string | null>(null);
	let loading = $state(false);
	let returnFocus: HTMLElement | null = null;

	async function ensureData() {
		if (buildings || loading) return;
		loading = true;
		loadError = null;
		try {
			buildings = await api.buildings();
		} catch (e) {
			loadError = errMessage(e);
		} finally {
			loading = false;
		}
	}

	$effect(() => {
		if (!dialog) return;
		if (open && !dialog.open) {
			returnFocus = document.activeElement as HTMLElement | null;
			query = '';
			active = 0;
			dialog.showModal();
			ensureData();
			tick().then(() => input?.focus());
		} else if (!open && dialog.open) {
			dialog.close();
		}
	});

	function onClose() {
		open = false;
		returnFocus?.focus?.();
	}

	// Нормалізація: регістр, різні апострофи, «№»
	function norm(s: string): string {
		return s
			.toLocaleLowerCase('uk')
			.replace(/[’'ʼ`"«»]/g, '')
			.replace(/№\s*/g, '№')
			.replace(/\s+/g, ' ')
			.trim();
	}

	const tokens = $derived(norm(query).split(' ').filter(Boolean));

	type Item =
		| { kind: 'page'; id: string; href: string; label: string; hint?: string }
		| { kind: 'building'; id: string; href: string; label: string; hint: string; cat: string };

	const pageItems = $derived.by((): Item[] => {
		const list = PALETTE_PAGES.filter((p) =>
			!p.only ? true : p.only === 'internal' ? isInternal(auth.user) : canUpload(auth.user)
		).map(({ href, label, hint }) => ({ kind: 'page' as const, id: 'p' + href, href, label, hint }));
		if (!tokens.length) return list;
		return list.filter((p) => {
			const hay = norm(p.label + ' ' + (p.hint ?? ''));
			return tokens.every((t) => hay.includes(t));
		});
	});

	// Абревіатури в назвах UMUNI → слова, якими шукають люди (і навпаки)
	const SYNONYMS: [RegExp, string][] = [
		[/азпсм|амбулатор/, 'азпсм амбулаторія сімейна медицина сімейний лікар'],
		[/цпмсд|первинн/, 'цпмсд центр первинної допомоги медицина'],
		[/днз|здо|дошкіл|садо|ясла/, 'днз здо садочок дитсадок садок дитячий садок'],
		[/зош|нвк|ліцей|гімназ|школ|ззсо/, 'школа зош ліцей гімназія нвк'],
		[/кнп|лікарн|госпітал|пологов|диспансер/, 'лікарня кнп медзаклад'],
		[/стоматолог/, 'стоматологія зубний'],
		[/виконком|виконавч|рада/, 'виконком міська рада адмінбудівля']
	];
	function expand(text: string): string {
		return SYNONYMS.filter(([re]) => re.test(text))
			.map(([, add]) => add)
			.join(' ');
	}

	const index = $derived(
		(buildings ?? []).map((b) => {
			const base = norm(`${b.name} ${b.address} ${b.category_short} ${catLabel(b.category_short)}`);
			return { b, hay: base + ' ' + expand(base), name: norm(b.name) };
		})
	);

	const MAX = 8;
	const buildingMatches = $derived.by(() => {
		if (!tokens.length) return { items: [] as Item[], total: 0 };
		const found = index.filter((x) => tokens.every((t) => x.hay.includes(t)));
		// Вище: збіги цілими словами («3» ≠ «35»), збіг у назві, збіг на початку назви
		const esc = (t: string) => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
		const words = tokens.map((t) => new RegExp(`(^|[\\s№(-])${esc(t)}($|[\\s,.)-])`));
		const score = (x: (typeof index)[number]) =>
			words.reduce((s, re, i) => s + (re.test(x.name) ? 3 : re.test(x.hay) ? 1 : 0) + (x.name.includes(tokens[i]) ? 1 : 0), 0) +
			(x.name.startsWith(tokens[0]) ? 1 : 0);
		const scored = found.map((x) => ({ ...x, s: score(x) }));
		scored.sort((a, b) => b.s - a.s || a.b.name.localeCompare(b.b.name, 'uk'));
		found.splice(0, found.length, ...scored);
		return {
			total: found.length,
			items: found.slice(0, MAX).map(
				({ b }): Item => ({
					kind: 'building',
					id: 'b' + b.id,
					href: `/object/${b.id}`,
					label: b.name,
					hint: b.address || 'адреса не вказана',
					cat: catLabel(b.category_short)
				})
			)
		};
	});

	// Порядок: спершу будівлі (коли щось шукаємо), потім сторінки
	const items = $derived([...buildingMatches.items, ...pageItems]);

	$effect(() => {
		// Скидаємо вибір при зміні запиту
		void query;
		active = 0;
	});

	function move(delta: number) {
		if (!items.length) return;
		active = (active + delta + items.length) % items.length;
		scrollActive();
	}

	async function scrollActive() {
		await tick();
		listEl?.querySelector(`[data-idx="${active}"]`)?.scrollIntoView({ block: 'nearest' });
	}

	function choose(i: number) {
		const it = items[i];
		if (!it) return;
		open = false;
		returnFocus = null;
		goto(it.href);
	}

	function keydown(e: KeyboardEvent) {
		if (e.key === 'ArrowDown') {
			e.preventDefault();
			move(1);
		} else if (e.key === 'ArrowUp') {
			e.preventDefault();
			move(-1);
		} else if (e.key === 'Home' && e.ctrlKey) {
			e.preventDefault();
			active = 0;
			scrollActive();
		} else if (e.key === 'End' && e.ctrlKey) {
			e.preventDefault();
			active = Math.max(0, items.length - 1);
			scrollActive();
		} else if (e.key === 'Enter') {
			e.preventDefault();
			choose(active);
		}
	}

	/** Підсвічує знайдені фрагменти */
	function parts(text: string): { t: string; m: boolean }[] {
		if (!tokens.length) return [{ t: text, m: false }];
		const low = text.toLocaleLowerCase('uk');
		const marks = new Array(text.length).fill(false);
		for (const tok of tokens) {
			let from = 0;
			let i: number;
			while (tok && (i = low.indexOf(tok, from)) !== -1) {
				for (let k = i; k < i + tok.length; k++) marks[k] = true;
				from = i + tok.length;
			}
		}
		const out: { t: string; m: boolean }[] = [];
		for (let k = 0; k < text.length; k++) {
			const last = out.at(-1);
			if (last && last.m === marks[k]) last.t += text[k];
			else out.push({ t: text[k], m: marks[k] });
		}
		return out;
	}

	function backdropClick(e: MouseEvent) {
		if (e.target === dialog) open = false;
	}

	const activeId = $derived(items[active] ? `cp-opt-${items[active].id}` : undefined);
	const firstPageIdx = $derived(buildingMatches.items.length);
</script>

<dialog
	bind:this={dialog}
	class="cp"
	aria-label="Пошук будівель і сторінок"
	onclose={onClose}
	onclick={backdropClick}
>
	<div class="cp-box">
		<div class="cp-input">
			<Icon name="search" size={22} />
			<input
				bind:this={input}
				bind:value={query}
				onkeydown={keydown}
				type="text"
				role="combobox"
				aria-expanded="true"
				aria-controls="cp-list"
				aria-autocomplete="list"
				aria-activedescendant={activeId}
				aria-describedby="cp-help"
				placeholder="Назва чи адреса будівлі, або сторінка…"
				autocomplete="off"
				spellcheck="false"
			/>
			<button type="button" class="cp-esc" onclick={() => (open = false)} aria-label="Закрити пошук"><span class="cp-esc-k">Esc</span><span class="cp-esc-t">Скасувати</span></button>
		</div>

		<ul id="cp-list" role="listbox" aria-label="Результати пошуку" bind:this={listEl}>
			{#if tokens.length && loading}
				<li class="cp-note" role="presentation">Завантажую перелік будівель…</li>
			{:else if tokens.length && loadError}
				<li class="cp-note" role="presentation">Не вдалося завантажити будівлі: {loadError}</li>
			{/if}
			{#each items as it, i (it.id)}
				{#if i === 0 && it.kind === 'building'}
					<li class="cp-group" role="presentation">
						Будівлі
						{#if buildingMatches.total > MAX}<span>· показано {MAX} з {buildingMatches.total}, уточніть запит</span>{/if}
					</li>
				{/if}
				{#if i === firstPageIdx}
					<li class="cp-group" role="presentation">{tokens.length ? 'Сторінки' : 'Перейти до сторінки'}</li>
				{/if}
				<!-- svelte-ignore a11y_click_events_have_key_events (клавіатура обробляється в полі пошуку: стрілки + Enter) -->
				<li
					id="cp-opt-{it.id}"
					role="option"
					aria-selected={i === active}
					data-idx={i}
					class="cp-opt"
					class:active={i === active}
					onclick={() => choose(i)}
					onpointermove={() => (active = i)}
				>
					<span class="cp-ico" aria-hidden="true">
						<Icon name={it.kind === 'building' ? 'building' : 'arrow-right'} size={18} />
					</span>
					<span class="cp-txt">
						<span class="cp-label">
							{#each parts(it.label) as p, k (k)}{#if p.m}<mark>{p.t}</mark>{:else}{p.t}{/if}{/each}
						</span>
						{#if it.hint}
							<span class="cp-hint">
								{#if it.kind === 'building'}{it.cat} · {/if}{#each parts(it.hint) as p, k (k)}{#if p.m}<mark>{p.t}</mark>{:else}{p.t}{/if}{/each}
							</span>
						{/if}
					</span>
					{#if i === active}<span class="cp-enter" aria-hidden="true">Enter ↵</span>{/if}
				</li>
			{/each}
			{#if tokens.length && !loading && !items.length}
				<li class="cp-empty" role="presentation">
					Нічого не знайдено за «{query.trim()}». Спробуйте частину назви («гімназія 3») або вулицю.
				</li>
			{/if}
		</ul>

		<p id="cp-help" class="cp-foot">
			<span><kbd>↑</kbd><kbd>↓</kbd> вибір</span>
			<span><kbd>Enter</kbd> відкрити</span>
			<span><kbd>Esc</kbd> закрити</span>
			<span class="cp-foot-r"><kbd>Ctrl</kbd>+<kbd>K</kbd> — відкрити пошук з будь-якої сторінки</span>
		</p>
		<p class="visually-hidden" aria-live="polite">
			{#if tokens.length}Знайдено будівель: {buildingMatches.total}, сторінок: {pageItems.length}{/if}
		</p>
	</div>
</dialog>

<style>
	.cp {
		width: min(44rem, calc(100vw - 2rem));
		max-height: min(36rem, calc(100vh - 6rem));
		margin: 9vh auto auto;
		padding: 0;
		border: 0;
		border-radius: 20px;
		background: var(--surface);
		color: var(--text);
		box-shadow:
			0 32px 80px -16px rgba(8, 20, 38, 0.55),
			0 0 0 1px rgba(8, 20, 38, 0.06);
		overflow: hidden;
	}
	.cp[open] {
		display: flex;
	}
	.cp::backdrop {
		background: rgba(10, 24, 42, 0.5);
		backdrop-filter: blur(3px);
	}
	@media (prefers-reduced-motion: no-preference) {
		.cp[open] {
			animation: cp-in 0.26s cubic-bezier(0.22, 1, 0.36, 1);
		}
		.cp[open]::backdrop {
			animation: cp-fade 0.2s ease-out;
		}
		@keyframes cp-in {
			from {
				opacity: 0;
				transform: translateY(-10px) scale(0.98);
			}
		}
		@keyframes cp-fade {
			from {
				opacity: 0;
			}
		}
	}
	.cp-box {
		display: flex;
		flex-direction: column;
		width: 100%;
		min-height: 0;
	}
	.cp-input {
		display: flex;
		align-items: center;
		gap: 0.7rem;
		padding: 0.85rem 1rem;
		border-bottom: 1px solid var(--line);
		color: var(--muted);
	}
	.cp-input input {
		flex: 1;
		min-width: 0;
		border: 0;
		outline: 0;
		font: inherit;
		font-size: 1.15rem;
		color: var(--text);
		background: transparent;
		padding: 0.35rem 0;
	}
	.cp-input input:focus-visible {
		box-shadow: none;
		outline: 0;
	}
	.cp-input:focus-within {
		box-shadow: inset 0 -2px 0 var(--accent);
	}
	.cp-esc {
		border: 1px solid var(--line-strong);
		background: #f4f6f9;
		border-radius: 6px;
		padding: 0.15rem 0.45rem;
		font: inherit;
		font-size: 0.8rem;
		color: var(--muted);
		cursor: pointer;
	}
	.cp-esc-t {
		display: none;
	}
	ul {
		list-style: none;
		margin: 0;
		padding: 0.4rem;
		overflow-y: auto;
		flex: 1;
		min-height: 0;
	}
	.cp-group {
		padding: 0.6rem 0.7rem 0.3rem;
		font-size: 0.75rem;
		font-weight: 700;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--muted);
	}
	.cp-group span {
		text-transform: none;
		letter-spacing: 0;
		font-weight: 400;
	}
	.cp-opt {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.55rem 0.7rem;
		border-radius: 10px;
		cursor: pointer;
	}
	.cp-opt.active {
		background: var(--accent-soft);
		box-shadow: inset 3px 0 0 var(--accent);
	}
	.cp-ico {
		display: grid;
		place-items: center;
		width: 2.1rem;
		height: 2.1rem;
		border-radius: 9px;
		background: #eef2f6;
		color: var(--navy-3);
		flex: none;
	}
	.cp-opt.active .cp-ico {
		background: #fff;
	}
	.cp-txt {
		display: flex;
		flex-direction: column;
		min-width: 0;
		flex: 1;
	}
	.cp-label {
		font-weight: 600;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.cp-hint {
		font-size: 0.875rem;
		color: var(--muted);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	mark {
		background: #ffe6a8;
		color: inherit;
		border-radius: 2px;
		padding: 0 1px;
	}
	.cp-enter {
		font-size: 0.75rem;
		color: var(--accent-dark);
		font-weight: 600;
		white-space: nowrap;
	}
	.cp-note,
	.cp-empty {
		padding: 1rem 0.8rem;
		color: var(--muted);
	}
	.cp-foot {
		display: flex;
		flex-wrap: wrap;
		gap: 0.3rem 1.1rem;
		margin: 0;
		padding: 0.6rem 1rem;
		border-top: 1px solid var(--line);
		background: #f7f9fb;
		font-size: 0.8rem;
		color: var(--muted);
	}
	.cp-foot-r {
		margin-left: auto;
	}
	kbd {
		display: inline-block;
		min-width: 1.5em;
		padding: 0 0.3em;
		margin-right: 0.2em;
		border: 1px solid var(--line-strong);
		border-bottom-width: 2px;
		border-radius: 4px;
		background: #fff;
		font: inherit;
		font-size: 0.75rem;
		text-align: center;
		color: var(--text);
	}
	/* Телефон: повноекранний пошук, як у нативних застосунках */
	@media (max-width: 640px) {
		.cp {
			width: 100vw;
			max-width: 100vw;
			height: 100dvh;
			max-height: 100dvh;
			margin: 0;
			border-radius: 0;
			box-shadow: none;
		}
		.cp-input {
			gap: 0.55rem;
			padding: calc(0.5rem + env(safe-area-inset-top, 0px)) calc(0.5rem + env(safe-area-inset-right, 0px)) 0.5rem calc(1rem + env(safe-area-inset-left, 0px));
			min-height: 60px;
		}
		.cp-input input {
			font-size: 17px;
			min-height: 44px;
		}
		.cp-esc {
			min-height: 44px;
			padding: 0 0.85rem;
			border: 0;
			border-radius: 12px;
			background: transparent;
			color: var(--accent);
			font-size: 1rem;
			font-weight: 600;
		}
		.cp-esc-k {
			display: none;
		}
		.cp-esc-t {
			display: inline;
		}
		ul {
			padding: 0.25rem 0.5rem calc(0.75rem + env(safe-area-inset-bottom, 0px));
			overscroll-behavior: contain;
		}
		.cp-opt {
			min-height: 56px;
			padding: 0.5rem 0.6rem;
		}
		.cp-opt:active {
			background: var(--accent-soft);
		}
		.cp-foot,
		.cp-enter {
			display: none;
		}
	}
	@media (max-width: 640px) and (prefers-reduced-motion: no-preference) {
		.cp[open] {
			animation: cp-up 0.3s cubic-bezier(0.22, 1, 0.36, 1);
		}
		@keyframes cp-up {
			from {
				opacity: 0.6;
				transform: translateY(24px);
			}
		}
	}
</style>
