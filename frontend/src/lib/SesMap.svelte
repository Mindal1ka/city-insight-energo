<script lang="ts">
	// Повноекранна мапа ефективності СЕС (Leaflet). Колір + форма маркера = клас K
	// (у публічному режимі — тип закладу). Маркери «хвилею» з'являються від центру,
	// вибраний об'єкт — плавний flyTo. prefers-reduced-motion вимикає анімації.
	import 'leaflet/dist/leaflet.css';
	import { onMount, untrack } from 'svelte';
	import type * as Leaflet from 'leaflet';
	import { kClassMeta, kText, type SesItem } from './api-ses.ts';
	import { categoryMeta, POLTAVA } from './api-map.ts';

	interface Props {
		items: SesItem[];
		/** 'class' — за класом K; 'category' — за типом закладу (публічний режим) */
		colorBy?: 'class' | 'category';
		selectedId?: number | null;
		onselect?: (id: number | null) => void;
		/** Зміна ключа — повторна «хвиля» (наприклад, зміна періоду) */
		waveKey?: string;
		/** Різниця «закрито знизу − закрито зверху» (px): вибраний маркер центруємо у видимій смузі */
		padBottom?: number;
	}

	let { items, colorBy = 'class', selectedId = null, onselect, waveKey = '', padBottom = 0 }: Props = $props();

	let el: HTMLDivElement;
	let L: typeof Leaflet | null = null;
	let map: Leaflet.Map | null = null;
	let layer: Leaflet.LayerGroup | null = null;
	let ready = $state(false);
	const markers = new Map<number, Leaflet.Marker>();
	let lastWave: string | null = null;
	let fitted = false;
	/** Поки користувач сам не рухав мапу — підганяємо вид під усі точки при зміні розміру */
	let autoFit = true;

	function fitAll(animate: boolean) {
		if (!map || !L) return;
		const pts = items.filter((i) => i.lat != null && i.lon != null && !i.approximate);
		const use = pts.length ? pts : items.filter((i) => i.lat != null);
		if (!use.length) return;
		const b = L.latLngBounds(use.map((p) => [p.lat!, p.lon!] as [number, number]));
		const narrow = el.clientWidth < 700;
		const opts = {
			paddingTopLeft: [20, narrow ? 190 : 120] as [number, number],
			paddingBottomRight: [20, 20] as [number, number]
		};
		if (animate && !reduced) map.flyToBounds(b, { ...opts, duration: 0.8 });
		else map.fitBounds(b, { ...opts, animate: false });
	}

	const reduced = typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches;

	function esc(s: string): string {
		return s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!);
	}

	function look(it: SesItem) {
		if (colorBy === 'class' && it.k_class) {
			const m = kClassMeta(it.k_class);
			return { color: m.color, glyph: m.glyph, word: m.short };
		}
		const c = categoryMeta(it.category_short);
		return { color: c.color, glyph: c.glyph, word: c.label };
	}

	function title(it: SesItem): string {
		const l = look(it);
		const k = colorBy === 'class' && it.k != null ? `, K ${kText(it.k)}` : '';
		return `${it.name} — ${l.word}${k}`;
	}

	function render() {
		if (!L || !map || !layer) return;
		const wave = !reduced && waveKey !== lastWave;
		lastWave = waveKey;
		layer.clearLayers();
		markers.clear();
		const pts = items.filter((i) => i.lat != null && i.lon != null) as (SesItem & { lat: number; lon: number })[];
		const c = map.getCenter();
		for (const it of pts) {
			const l = look(it);
			const dist = Math.hypot(it.lat - c.lat, (it.lon - c.lng) * 0.65);
			const delay = wave ? Math.min(700, Math.round(dist * 9000)) : 0;
			const mute = colorBy === 'class' && (it.k_class === 'Без СЕС' || it.k_class === 'Немає даних');
			const html = `<span class="sm-mk${mute ? ' mute' : ''}${wave ? ' wave' : ''}${it.id === selectedId ? ' sel' : ''}" style="--c:${l.color};--d:${delay}ms"><svg viewBox="0 0 10 10" aria-hidden="true"><path d="${l.glyph}"/></svg></span>`;
			const m = L.marker([it.lat, it.lon], {
				icon: L.divIcon({ className: 'sm-icon', html, iconSize: [22, 22], iconAnchor: [11, 11] }),
				title: esc(title(it)),
				alt: title(it),
				keyboard: true,
				riseOnHover: true,
				zIndexOffset: it.id === selectedId ? 1000 : mute ? -500 : 0
			});
			m.on('click', () => onselect?.(it.id));
			m.addTo(layer);
			const icon = m.getElement();
			if (icon) {
				icon.setAttribute('role', 'button');
				icon.setAttribute('aria-label', title(it));
				icon.addEventListener('keydown', (e) => {
					if (e.key === 'Enter' || e.key === ' ') {
						e.preventDefault();
						e.stopPropagation();
						onselect?.(it.id);
					}
				});
			}
			markers.set(it.id, m);
		}
		if (!fitted && pts.length) {
			fitted = true;
			fitAll(false);
		}
	}

	function focusSelected(id: number | null) {
		if (!map || !L) return;
		for (const [mid, m] of markers) {
			const n = m.getElement()?.querySelector('.sm-mk');
			n?.classList.toggle('sel', mid === id);
			m.setZIndexOffset(mid === id ? 1000 : n?.classList.contains('mute') ? -500 : 0);
		}
		if (id == null) return;
		autoFit = false;
		const m = markers.get(id);
		if (!m) return;
		const z = Math.max(map.getZoom(), 15);
		let target = m.getLatLng();
		if (padBottom) target = map.unproject(map.project(target, z).add([0, padBottom / 2]), z);
		if (reduced) map.setView(target, z, { animate: false });
		else map.flyTo(target, z, { duration: 0.8, easeLinearity: 0.25 });
	}

	export function resetView() {
		autoFit = true;
		fitAll(true);
	}

	onMount(() => {
		let alive = true;
		import('leaflet').then((mod) => {
			if (!alive) return;
			L = (mod as unknown as { default?: typeof Leaflet }).default ?? (mod as unknown as typeof Leaflet);
			map = L.map(el, { zoomControl: false, zoomSnap: 0.25, preferCanvas: false }).setView(POLTAVA, 12);
			map.attributionControl.setPrefix(false);
			L.control.zoom({ position: 'bottomright', zoomInTitle: 'Наблизити', zoomOutTitle: 'Віддалити' }).addTo(map);
			L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
				maxZoom: 19,
				className: 'sm-tiles',
				attribution:
					'&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">учасники OpenStreetMap</a>'
			}).addTo(map);
			map.on('dragstart', () => (autoFit = false));
			el.addEventListener('wheel', () => (autoFit = false), { passive: true });
			layer = L.layerGroup().addTo(map);
			map.on('click', () => onselect?.(null));
			ready = true;
		});
		const ro = new ResizeObserver(() => {
			map?.invalidateSize();
			if (autoFit && selectedId == null) fitAll(false);
		});
		ro.observe(el);
		return () => {
			alive = false;
			ro.disconnect();
			map?.remove();
			map = null;
		};
	});

	$effect(() => {
		// залежності: items, colorBy, waveKey
		void items;
		void colorBy;
		void waveKey;
		if (ready) untrack(render);
	});

	$effect(() => {
		const id = selectedId;
		if (ready) focusSelected(id);
	});
</script>

<div class="sm-root" bind:this={el} role="region" aria-label="Мапа комунальних об’єктів"></div>

<style>
	.sm-root {
		position: absolute;
		inset: 0;
		background: #e8edf2;
		z-index: 0;
	}
	.sm-root :global(.sm-icon) {
		background: none;
		border: 0;
	}
	.sm-root :global(.sm-icon:focus-visible) {
		outline: none;
	}
	.sm-root :global(.sm-icon:focus-visible .sm-mk) {
		box-shadow: 0 0 0 3px #fff, 0 0 0 6px var(--focus, #ffbf47);
	}
	.sm-root :global(.sm-mk) {
		display: grid;
		place-items: center;
		width: 22px;
		height: 22px;
		border-radius: 50%;
		background: #fff;
		box-shadow: 0 1px 3px rgba(15, 35, 65, 0.35);
		transition: transform 0.2s var(--ease-spring, ease);
	}
	.sm-root :global(.sm-mk svg) {
		width: 16px;
		height: 16px;
		fill: var(--c);
		stroke: rgba(0, 0, 0, 0.18);
		stroke-width: 0.5;
	}
	.sm-root :global(.sm-mk.mute) {
		width: 15px;
		height: 15px;
		margin: 3.5px;
		opacity: 0.85;
	}
	.sm-root :global(.sm-mk.mute svg) {
		width: 11px;
		height: 11px;
	}
	.sm-root :global(.sm-icon:hover .sm-mk) {
		transform: scale(1.25);
	}
	.sm-root :global(.sm-mk.sel) {
		transform: scale(1.55);
		box-shadow: 0 0 0 3px var(--c), 0 4px 12px rgba(15, 35, 65, 0.4);
	}
	.sm-root :global(.sm-mk.wave) {
		animation: sm-in 0.45s var(--ease-spring, ease) backwards;
		animation-delay: var(--d);
	}
	@keyframes -global-sm-in {
		from {
			opacity: 0;
			transform: scale(0.2);
		}
		to {
			opacity: 1;
			transform: scale(1);
		}
	}
	.sm-root :global(.leaflet-control-zoom) {
		border: 0;
		box-shadow: 0 2px 10px rgba(15, 35, 65, 0.18);
		border-radius: 12px;
		overflow: hidden;
	}
	.sm-root :global(.leaflet-control-attribution) {
		font-size: 0.65rem;
	}
	@media (prefers-reduced-motion: reduce) {
		.sm-root :global(.sm-mk) {
			animation: none !important;
			transition: none;
		}
	}
</style>
