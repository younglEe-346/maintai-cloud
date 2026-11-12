// Graphique du risque, dessiné en SVG à la main (aucune bibliothèque de graphiques).
// Axe horizontal : les mesures dans l'ordre (la plus ancienne à gauche).
// Axe vertical : le risque de 0 à 100 %. Ligne pointillée : le seuil d'alerte.
import type { MouseEvent } from "react";
import { useI18n } from "../i18n";

export interface RiskPoint { risk: number; threshold: number; }

const W = 640, H = 240;                                  // taille logique ; le SVG s'adapte à la largeur
const PAD = { left: 44, right: 12, top: 12, bottom: 28 };
const PLOT_W = W - PAD.left - PAD.right, PLOT_H = H - PAD.top - PAD.bottom;

export default function RiskChart({ points, selected, onSelect }:
  { points: RiskPoint[]; selected: number; onSelect: (index: number) => void }) {
  const { t, formatPercent } = useI18n();
  const n = points.length;
  const x = (i: number) => PAD.left + (n === 1 ? PLOT_W / 2 : (i / (n - 1)) * PLOT_W);
  const y = (risk: number) => PAD.top + (1 - risk) * PLOT_H;

  const line = points.map((p, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(p.risk).toFixed(1)}`).join(" ");
  const threshold = points[n - 1].threshold;   // seuil de la mesure la plus récente

  // Clic n'importe où sur la zone : on choisit la mesure la plus proche horizontalement.
  function pick(e: MouseEvent<SVGRectElement>) {
    const box = e.currentTarget.getBoundingClientRect();
    const ratio = (e.clientX - box.left) / box.width;
    onSelect(Math.min(n - 1, Math.max(0, Math.round(ratio * (n - 1)))));
  }

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="h-auto w-full"
      role="img"
      aria-label={t("detail.chartAria", {
        n: String(n), last: formatPercent(points[n - 1].risk), threshold: formatPercent(threshold),
      })}
    >
      {/* graduations horizontales 0 %, 25 %, 50 %, 75 %, 100 % */}
      {[0, 0.25, 0.5, 0.75, 1].map((v) => (
        <g key={v}>
          <line x1={PAD.left} x2={W - PAD.right} y1={y(v)} y2={y(v)} className="stroke-line-strong" />
          <text x={PAD.left - 6} y={y(v) + 4} textAnchor="end" className="fill-ink-muted text-[11px]">
            {Math.round(v * 100)} %
          </text>
        </g>
      ))}

      {/* seuil d'alerte */}
      <line x1={PAD.left} x2={W - PAD.right} y1={y(threshold)} y2={y(threshold)}
        strokeDasharray="6 4" className="stroke-danger" />
      <text x={W - PAD.right} y={y(threshold) - 5} textAnchor="end" className="fill-danger text-[11px]">
        {t("detail.threshold", { value: formatPercent(threshold) })}
      </text>

      {/* courbe et points (rouges au-dessus du seuil) */}
      <path d={line} fill="none" strokeWidth={1.5} className="stroke-accent" />
      {points.map((p, i) => (
        <circle key={i} cx={x(i)} cy={y(p.risk)} r={n > 80 ? 2 : 3}
          className={p.risk >= p.threshold ? "fill-danger" : "fill-accent"} />
      ))}

      {/* mesure sélectionnée */}
      <line x1={x(selected)} x2={x(selected)} y1={PAD.top} y2={H - PAD.bottom} className="stroke-ink-faint" />
      <circle cx={x(selected)} cy={y(points[selected].risk)} r={6} fill="none" strokeWidth={2} className="stroke-ink" />

      <text x={PAD.left} y={H - 8} className="fill-ink-muted text-[11px]">{t("detail.older")}</text>
      <text x={W - PAD.right} y={H - 8} textAnchor="end" className="fill-ink-muted text-[11px]">{t("detail.newer")}</text>

      {/* zone cliquable transparente posée au-dessus */}
      <rect x={PAD.left} y={PAD.top} width={PLOT_W} height={PLOT_H} fill="transparent"
        className="cursor-pointer" onClick={pick} />
    </svg>
  );
}
