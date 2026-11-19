// Зведення «Розподілення енергії» для громади: сума по всіх об'єктах з СЕС
import type { SiteDetail, SiteDistribution, SiteHour } from './api.ts';

export interface Community {
	count: number;
	distribution: SiteDistribution;
	hourly: SiteHour[];
	battery_capacity_kwh: number;
}

export function aggregate(details: SiteDetail[]): Community {
	const ses = details.filter((d) => d.ses);
	const hours = new Map<number, { gen: number; cons: number; soc: number; cap: number; fc: boolean }>();
	let cap = 0;
	for (const d of ses) {
		const c = d.ses!.battery_kwh;
		cap += c;
		for (const h of d.hourly) {
			const a = hours.get(h.hour) ?? { gen: 0, cons: 0, soc: 0, cap: 0, fc: h.forecast };
			a.gen += h.gen_kwh;
			a.cons += h.cons_kwh;
			if (h.soc_pct !== null) {
				a.soc += (h.soc_pct / 100) * c;
				a.cap += c;
			}
			a.fc = a.fc && h.forecast;
			hours.set(h.hour, a);
		}
	}
	const hourly: SiteHour[] = [...hours.entries()]
		.sort((a, b) => a[0] - b[0])
		.map(([hour, a]) => ({
			hour,
			gen_kwh: a.gen,
			cons_kwh: a.cons,
			soc_pct: a.cap > 0 ? (a.soc / a.cap) * 100 : null,
			forecast: a.fc
		}));
	const peak = hourly.reduce<SiteHour | null>((p, h) => (!p || h.cons_kwh > p.cons_kwh ? h : p), null);

	const sum = (f: (d: SiteDistribution) => number | null) =>
		ses.reduce((a, d) => a + (f(d.distribution) ?? 0), 0);
	const batNow = sum((d) => d.battery_kwh_now);
	const available = sum((d) => d.available_kwh);
	const need = sum((d) => d.need_kwh_rest_of_day);

	return {
		count: ses.length,
		battery_capacity_kwh: cap,
		hourly,
		distribution: {
			peak_kw: peak?.cons_kwh ?? 0,
			peak_hour: peak?.hour ?? 0,
			battery_kwh_now: batNow,
			battery_soc_pct: cap > 0 ? (batNow / cap) * 100 : null,
			solar_kw_now: sum((d) => d.solar_kw_now),
			solar_kwh_rest_of_day: sum((d) => d.solar_kwh_rest_of_day),
			need_kwh_rest_of_day: need,
			available_kwh: available,
			// Сума балансів об'єктів — збігається з «Балансом громади» на сторінці вибору
			balance_kwh: sum((d) => d.balance_kwh),
			enough: sum((d) => d.balance_kwh) >= 0,
			reserve_to_grid_kwh: sum((d) => d.reserve_to_grid_kwh)
		}
	};
}
