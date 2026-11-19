<script lang="ts">
	// Повноекранна мапа ефективності СЕС (Leaflet). Колір + форма маркера = клас K
	// (у публічному режимі — тип закладу). Маркери «хвилею» з'являються від центру,
	// вибраний об'єкт — плавний flyTo. prefers-reduced-motion вимикає анімації.
	import 'leaflet/dist/leaflet.css';
	import 'leaflet.markercluster/dist/MarkerCluster.css';
	import { onMount, untrack } from 'svelte';
	import type * as Leaflet from 'leaflet';
	import { kClassMeta, kText, type KClass, type SesItem } from './api-ses.ts';
	import { categoryMeta, POLTAVA } from './api-map.ts';
	import type { Zone } from './api-v2.ts';
	import { ZONE_COLORS } from './zone-meta.ts';

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
		/** Зони обміну надлишком (кола навколо якоря) */
		zones?: Zone[];
		showZones?: boolean;
		selectedZoneId?: number | null;
		onzone?: (id: number | null) => void;
	}

	let { items, colorBy = 'class', selectedId = null, onselect, waveKey = '', padBottom = 0, zones = [], showZones = true, selectedZoneId = null, onzone }: Props = $props();

	let el: HTMLDivElement;
	let L: typeof Leaflet | null = null;
	let map: Leaflet.Map | null = null;
	let layer: Leaflet.MarkerClusterGroup | null = null;
	let zoneGroup: Leaflet.LayerGroup | null = null;
	let ready = $state(false);
	const markers = new Map<number, Leaflet.Marker>();
	const byId = new Map<number, SesItem>();
	let prevSel: number | null = null;
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

	function clsKey(it: SesItem): string {
		return colorBy === 'class' && it.k_class ? it.k_class : 'cat:' + it.category_short;
	}

	function isMute(it: SesItem): boolean {
		return colorBy === 'class' && (it.k_class === 'Без СЕС' || it.k_class === 'Немає даних');
	}

	function mkHtml(it: SesItem, sel: boolean, wave = false, delay = 0): string {
		const l = look(it);
		return `<span class="sm-mk${isMute(it) ? ' mute' : ''}${wave ? ' wave' : ''}${sel ? ' sel' : ''}" style="--c:${l.color};--d:${delay}ms"><svg viewBox="0 0 10 10" aria-hidden="true"><path d="${l.glyph}"/></svg></span>`;
	}

	/** Колір сегмента кластера за ключем класу */
	function keyColor(k: string): string {
		if (k.startsWith('cat:')) return categoryMeta(k.slice(4)).color;
		return kClassMeta(k as KClass).color;
	}

	function clusterIcon(c: Leaflet.MarkerCluster): Leaflet.DivIcon {
		const counts = new Map<string, number>();
		const kids = c.getAllChildMarkers();
		for (const m of kids) {
			const k = (m.options as { kcls?: string }).kcls ?? '';
			counts.set(k, (counts.get(k) ?? 0) + 1);
		}
		const n = kids.length;
		let acc = 0;
		const stops: string[] = [];
		for (const [k, v] of [...counts].sort((a, b) => b[1] - a[1])) {
			const from = (acc / n) * 360;
			acc += v;
			stops.push(`${keyColor(k)} ${from}deg ${(acc / n) * 360}deg`);
		}
		const size = n < 10 ? 38 : n < 50 ? 44 : 50;
		return L!.divIcon({
			className: 'sm-icon',
			html: `<span class="sm-cl" style="background:conic-gradient(${stops.join(',')});width:${size}px;height:${size}px"><b>${n}</b></span>`,
			iconSize: [size, size]
		});
	}

	function render() {
		if (!L || !map || !layer) return;
		const wave = !reduced && waveKey !== lastWave;
		lastWave = waveKey;
		layer.clearLayers();
		markers.clear();
		byId.clear();
		const pts = items.filter((i) => i.lat != null && i.lon != null) as (SesItem & { lat: number; lon: number })[];
		const c = map.getCenter();
		for (const it of pts) {
			const dist = Math.hypot(it.lat - c.lat, (it.lon - c.lng) * 0.65);
			const delay = wave ? Math.min(700, Math.round(dist * 9000)) : 0;
			const mute = colorBy === 'class' && (it.k_class === 'Без СЕС' || it.k_class === 'Немає даних');
			const m = L.marker([it.lat, it.lon], {
				icon: L.divIcon({ className: 'sm-icon', html: mkHtml(it, it.id === selectedId, wave, delay), iconSize: [22, 22], iconAnchor: [11, 11] }),
				title: esc(title(it)),
				alt: title(it),
				keyboard: true,
				riseOnHover: true,
				zIndexOffset: it.id === selectedId ? 1000 : mute ? -500 : 0,
				kcls: clsKey(it)
			} as Leaflet.MarkerOptions);
			m.on('click', () => onselect?.(it.id));
			m.on('add', () => {
				const icon = m.getElement();
				if (!icon) return;
				icon.setAttribute('role', 'button');
				icon.setAttribute('aria-label', title(it));
				icon.addEventListener('keydown', (e) => {
					if (e.key === 'Enter' || e.key === ' ') {
						e.preventDefault();
						e.stopPropagation();
						onselect?.(it.id);
					}
				});
			});
			byId.set(it.id, it);
			layer.addLayer(m);
			markers.set(it.id, m);
		}
		prevSel = selectedId;
		if (!fitted && pts.length) {
			fitted = true;
			fitAll(false);
		}
	}

	function renderZones() {
		if (!L || !map || !zoneGroup) return;
		zoneGroup.clearLayers();
		if (!showZones) return;
		const renderer = L.svg({ pane: 'zones' });
		for (const z of zones) {
			const color = ZONE_COLORS[z.status ?? 'no_ses'];
			const sel = z.id === selectedZoneId;
			const c = L.circle([z.lat, z.lon], {
				radius: z.radius_m,
				pane: 'zones',
				renderer,
				color,
				weight: sel ? 3 : 1.5,
				opacity: sel ? 0.95 : 0.6,
				fillColor: color,
				fillOpacity: sel ? 0.22 : 0.1,
				bubblingMouseEvents: false
			});
			c.on('click', () => onzone?.(z.id));
			c.bindTooltip(esc(z.name), { sticky: true, direction: 'top' });
			zoneGroup.addLayer(c);
			if ((z.shareable_kwh ?? 0) > 0) {
				const donors = z.members.filter((m) => m.role === 'donor');
				const takers = z.members.filter((m) => m.role === 'taker');
				for (const d of donors)
					for (const t of takers)
						zoneGroup.addLayer(
							L.polyline(
								[
									[d.lat, d.lon],
									[t.lat, t.lon]
								],
								{ pane: 'zones', renderer, color: ZONE_COLORS.surplus, weight: 2, opacity: 0.8, dashArray: '6 6', interactive: false }
							)
						);
			}
		}
	}

	function focusSelected(id: number | null) {
		if (!map || !L) return;
		for (const mid of new Set([prevSel, id])) {
			if (mid == null) continue;
			const it = byId.get(mid);
			const m = markers.get(mid);
			if (!it || !m) continue;
			const sel = mid === id;
			m.setIcon(L.divIcon({ className: 'sm-icon', html: mkHtml(it, sel), iconSize: [22, 22], iconAnchor: [11, 11] }));
			m.setZIndexOffset(sel ? 1000 : isMute(it) ? -500 : 0);
		}
		prevSel = id;
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
		import('leaflet').then(async (mod) => {
			if (!alive) return;
			L = (mod as unknown as { default?: typeof Leaflet }).default ?? (mod as unknown as typeof Leaflet);
			// markercluster чекає глобальний L
			(window as unknown as { L: typeof Leaflet }).L = L;
			await import('leaflet.markercluster');
			if (!alive) return;
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
			map.createPane('zones').style.zIndex = '380';
				zoneGroup = L.layerGroup().addTo(map);
				layer = L.markerClusterGroup({
				showCoverageOnHover: false,
				maxClusterRadius: 48,
				disableClusteringAtZoom: 15,
				spiderfyOnMaxZoom: false,
				animate: !reduced,
				iconCreateFunction: clusterIcon
			}).addTo(map);
			map.on('click', () => {
					onselect?.(null);
					onzone?.(null);
				});
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
		void zones;
		void showZones;
		void selectedZoneId;
		if (ready) untrack(renderZones);
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
	.sm-root :global(.sm-cl) {
		display: grid;
		place-items: center;
		border-radius: 50%;
		box-shadow: 0 1px 4px rgba(15, 35, 65, 0.4);
	}
	.sm-root :global(.sm-cl b) {
		display: grid;
		place-items: center;
		width: calc(100% - 10px);
		height: calc(100% - 10px);
		border-radius: 50%;
		background: #fff;
		color: #0f1b2d;
		font-size: 0.8rem;
		font-variant-numeric: tabular-nums;
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
