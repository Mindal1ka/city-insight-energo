<script lang="ts">
	// Сторінка «Оновити дані»: завантаження нового XLSX з UMUNI, після чого все перераховується автоматично
	import { api, errMessage, type UploadResult } from '#lib/api.ts';
	import { num, pct, dateTime } from '#lib/format.ts';

	let file = $state<File | null>(null);
	let busy = $state(false);
	let result = $state<UploadResult | null>(null);
	let error = $state<string | null>(null);

	function pick(e: Event) {
		const input = e.currentTarget as HTMLInputElement;
		file = input.files?.[0] ?? null;
		result = null;
		error = null;
	}

	async function send(e: SubmitEvent) {
		e.preventDefault();
		if (!file) {
			error = 'Оберіть файл XLSX.';
			return;
		}
		if (!file.name.toLowerCase().endsWith('.xlsx')) {
			error = 'Потрібен файл у форматі XLSX (вивантаження з UMUNI).';
			return;
		}
		busy = true;
		error = null;
		result = null;
		try {
			result = await api.upload(file);
		} catch (err) {
			error = errMessage(err);
		} finally {
			busy = false;
		}
	}

	function kindLabel(kind: string): string {
		if (kind === 'buildings') return 'Характеристики будівель (реєстр)';
		if (kind === 'annual') return 'Річний звіт про використання ресурсів';
		return kind;
	}
</script>

<svelte:head><title>Оновити дані · City Insight Map · Енергія</title></svelte:head>

<div class="page-head">
	<div>
		<h1>Оновити дані</h1>
		<p class="lead">
			Завантажте свіже вивантаження з UMUNI — і рейтинг, класи, дефекти даних та розрахунок СЕС
			перерахуються автоматично. Розробник для цього не потрібен.
		</p>
	</div>
</div>

<div class="grid-2">
	<form class="card" onsubmit={send}>
		<h2>Завантаження файлу</h2>
		<div class="field">
			<label for="file">Файл XLSX з UMUNI</label>
			<input id="file" type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" onchange={pick} aria-describedby="file-help" />
			<p id="file-help" class="muted small">
				Підходять звіти «Характеристики будівель» (Buildings_Info_Report) та «Річне використання
				ресурсів» за будь-який рік. Файл завантажуйте як є, без змін.
			</p>
		</div>
		<button class="btn" type="submit" disabled={busy || !file}>
			{busy ? 'Завантаження і перерахунок…' : 'Завантажити й перерахувати'}
		</button>

		<div aria-live="polite">
			{#if error}
				<div class="notice notice-error result" role="alert">
					<p><strong>Файл не прийнято.</strong> {error}</p>
				</div>
			{/if}
			{#if result}
				<div class="notice notice-ok result">
					<p><strong>Готово! Дані оновлено.</strong> Розпізнано: {kindLabel(result.kind)}.</p>
					<ul>
						<li>Будівель у базі: <strong>{num(result.summary.buildings)}</strong>, у рейтингу: <strong>{num(result.summary.in_rating)}</strong></li>
						<li>Базовий рік рейтингу: <strong>{result.summary.base_year ?? '—'}</strong></li>
						{#each Object.entries(result.summary.years) as [y, s] (y)}
							<li>
								{y}: вивантаження від {dateTime(s.created)}{s.partial ? `, неповний рік (${pct(s.coverage)})` : ''}
							</li>
						{/each}
						<li>Дефектів даних: <strong>{num(result.summary.defects)}</strong> на {num(result.summary.defect_buildings)} будівлях</li>
					</ul>
					<p><a href="/">Переглянути огляд</a> · <a href="/rating">Рейтинг</a> · <a href="/defects">Якість даних</a></p>
				</div>
			{/if}
		</div>
	</form>

	<section class="card">
		<h2>Як це працює</h2>
		<ol class="steps">
			<li>Вивантажте звіт з UMUNI у форматі XLSX.</li>
			<li>Завантажте його тут. Система сама визначить тип звіту та рік.</li>
			<li>Якщо за рік уже є файл, використовується новіший за датою вивантаження.</li>
			<li>Усі показники, рейтинг і перелік дефектів перераховуються одразу після завантаження.</li>
		</ol>
		<p class="muted small">
			Неповний поточний рік позначається окремо: його не порівнюємо напряму з повним роком.
		</p>
	</section>
</div>

<style>
	form .field {
		margin-bottom: 1rem;
	}
	input[type='file'] {
		font: inherit;
		padding: 0.5rem;
		border: 1px dashed var(--line-strong);
		border-radius: 6px;
		background: #fafbfc;
	}
	.result {
		margin-top: 1rem;
	}
	.result ul {
		margin: 0 0 0.5rem;
		padding-left: 1.2rem;
	}
	.steps {
		padding-left: 1.2rem;
	}
	.steps li {
		margin-bottom: 0.4rem;
	}
</style>
