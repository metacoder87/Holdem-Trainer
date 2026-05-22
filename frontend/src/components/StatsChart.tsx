import { useEffect, useRef } from 'react';
import { LineChart } from 'echarts/charts';
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import { graphic, init, use, type ECharts, type EChartsCoreOption } from 'echarts/core';

use([LineChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer]);

/**
 * One row on the chart. ``value`` is always required; the optional
 * fields let a single row carry multiple aligned series:
 *
 *  - ``rolling_value``        — pooled rolling-window value (smoothed line).
 *  - ``realized_cumulative_bb`` + ``ev_cumulative_bb`` — the realized
 *    vs all-in-EV-adjusted cumulative pair. When both are present and
 *    differ, the band between them visualizes the "luck" component
 *    (a staple of PokerTracker/HM2 analysis).
 *  - ``ci_lower`` + ``ci_upper`` — 95% credible band, rendered as a
 *    filled region around the main line. Used for Bayesian-aware
 *    rate stat trending.
 */
export interface DataPoint {
  label: string;
  value: number;
  rolling_value?: number;
  realized_cumulative_bb?: number;
  ev_cumulative_bb?: number | null;
  ci_lower?: number;
  ci_upper?: number;
}

interface StatsChartProps {
  data: DataPoint[];
  color?: string;
  label?: string;
  height?: number;
  /**
   * When true and the data carries ``realized_cumulative_bb`` /
   * ``ev_cumulative_bb`` fields, a second EV-adjusted line is drawn
   * and the gap between the two is filled.
   */
  showEvAdjusted?: boolean;
  /**
   * When true and any data row carries ``ci_lower`` / ``ci_upper``,
   * the 95% credible band is rendered as a translucent area between
   * the two bounds.
   */
  showConfidenceBand?: boolean;
  /**
   * When true and the data carries ``rolling_value`` fields, an
   * additional smoothed series is overlaid.
   */
  showRolling?: boolean;
}

export default function StatsChart({
  data,
  color = '#28f4ff',
  label,
  height = 300,
  showEvAdjusted = false,
  showConfidenceBand = false,
  showRolling = false,
}: StatsChartProps) {
  const chartRef = useRef<HTMLDivElement>(null);
  const instanceRef = useRef<ECharts | null>(null);

  useEffect(() => {
    if (!chartRef.current) return;

    if (!instanceRef.current) {
      instanceRef.current = init(chartRef.current);
    }

    const chart = instanceRef.current;

    // Detect what optional series the caller asked for AND that the
    // data actually carries. Belt + suspenders: a flag without data
    // shouldn't render an empty series.
    const hasEv =
      showEvAdjusted &&
      data.some(
        (d) =>
          d.realized_cumulative_bb !== undefined &&
          d.realized_cumulative_bb !== null
      );
    const hasBand =
      showConfidenceBand &&
      data.some((d) => d.ci_lower !== undefined && d.ci_upper !== undefined);
    const hasRolling =
      showRolling && data.some((d) => d.rolling_value !== undefined);

    // Choose what the primary line displays. For the EV-adjusted
    // case we plot realized cumulative; otherwise plot raw value.
    const primaryValues = hasEv
      ? data.map((d) => d.realized_cumulative_bb ?? 0)
      : data.map((d) => d.value);

    type SeriesEntry = Record<string, unknown>;
    const series: SeriesEntry[] = [
      {
        name: hasEv ? 'Realized (cum BB)' : label || 'Value',
        type: 'line',
        smooth: true,
        showSymbol: false,
        data: primaryValues,
        lineStyle: {
          width: 3,
          color: new graphic.LinearGradient(0, 0, 1, 0, [
            { offset: 0, color },
            { offset: 1, color: '#ffffff' },
          ]),
        },
        areaStyle: hasEv
          ? undefined
          : {
              opacity: 0.18,
              color: new graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color },
                { offset: 1, color: 'transparent' },
              ]),
            },
      },
    ];

    if (hasEv) {
      // EV-adjusted (skill) line. Dashed for visual distinction.
      series.push({
        name: 'EV-adjusted (skill)',
        type: 'line',
        smooth: true,
        showSymbol: false,
        data: data.map((d) =>
          d.ev_cumulative_bb === null || d.ev_cumulative_bb === undefined
            ? null
            : d.ev_cumulative_bb
        ),
        lineStyle: {
          width: 2,
          color: '#ffb547',
          type: 'dashed',
        },
      });
    }

    if (hasRolling) {
      series.push({
        name: 'Rolling avg',
        type: 'line',
        smooth: true,
        showSymbol: false,
        data: data.map((d) => (d.rolling_value === undefined ? null : d.rolling_value)),
        lineStyle: {
          width: 2,
          color: '#a0e8b3',
          type: 'dotted',
        },
      });
    }

    if (hasBand) {
      // Confidence band: two stacked transparent series, the upper
      // bound filled down to the lower. ECharts doesn't have a
      // native band primitive so we render lower as an invisible
      // base then upper-lower as a stacked area.
      const lower = data.map((d) => d.ci_lower ?? 0);
      const upperDelta = data.map(
        (d) => (d.ci_upper ?? 0) - (d.ci_lower ?? 0)
      );
      series.unshift(
        {
          name: 'CI floor',
          type: 'line',
          stack: 'ci',
          symbol: 'none',
          showSymbol: false,
          lineStyle: { opacity: 0 },
          areaStyle: { opacity: 0 },
          data: lower,
          tooltip: { show: false },
          silent: true,
        },
        {
          name: 'CI band',
          type: 'line',
          stack: 'ci',
          symbol: 'none',
          showSymbol: false,
          lineStyle: { opacity: 0 },
          areaStyle: {
            opacity: 0.18,
            color,
          },
          data: upperDelta,
          tooltip: { show: false },
          silent: true,
        }
      );
    }

    const option: EChartsCoreOption = {
      backgroundColor: 'transparent',
      grid: {
        top: 40,
        right: 20,
        bottom: 30,
        left: 40,
        containLabel: true,
      },
      tooltip: {
        trigger: 'axis',
        backgroundColor: '#0f1a24',
        borderColor: '#2d3b4f',
        textStyle: { color: '#b7c6da' },
      },
      legend: {
        show: hasEv || hasRolling,
        top: 4,
        right: 8,
        textStyle: { color: '#7b8ba3', fontSize: 11 },
        // Hide the synthetic CI-floor / CI-band entries from the
        // legend; they're not user-relevant lines.
        data: series
          .filter(
            (s) => s.name !== 'CI floor' && s.name !== 'CI band'
          )
          .map((s) => s.name as string),
      },
      xAxis: {
        type: 'category',
        data: data.map((d) => d.label),
        axisLine: { lineStyle: { color: '#2d3b4f' } },
        axisLabel: { color: '#7b8ba3' },
      },
      yAxis: {
        type: 'value',
        splitLine: { lineStyle: { color: '#1a2634' } },
        axisLabel: { color: '#7b8ba3' },
      },
      series,
    };

    chart.setOption(option, true);

    const resizeObserver = new ResizeObserver(() => chart.resize());
    resizeObserver.observe(chartRef.current);

    return () => {
      resizeObserver.disconnect();
      chart.dispose();
      instanceRef.current = null;
    };
  }, [data, color, label, showEvAdjusted, showConfidenceBand, showRolling]);

  return <div ref={chartRef} style={{ width: '100%', height }} />;
}
