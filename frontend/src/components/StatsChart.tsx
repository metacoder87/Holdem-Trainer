import { useEffect, useRef } from 'react';
import { LineChart } from 'echarts/charts';
import { GridComponent, TooltipComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import { graphic, init, use, type ECharts, type EChartsCoreOption } from 'echarts/core';

use([LineChart, GridComponent, TooltipComponent, CanvasRenderer]);

interface DataPoint {
    label: string;
    value: number;
}

interface StatsChartProps {
    data: DataPoint[];
    color?: string;
    label?: string;
    height?: number;
}

export default function StatsChart({ data, color = '#28f4ff', label, height = 300 }: StatsChartProps) {
    const chartRef = useRef<HTMLDivElement>(null);
    const instanceRef = useRef<ECharts | null>(null);

    useEffect(() => {
        if (!chartRef.current) return;

        // Initialize chart
        if (!instanceRef.current) {
            instanceRef.current = init(chartRef.current);
        }

        const chart = instanceRef.current;

        const option: EChartsCoreOption = {
            backgroundColor: 'transparent',
            grid: {
                top: 30,
                right: 20,
                bottom: 20,
                left: 40,
                containLabel: true
            },
            tooltip: {
                trigger: 'axis',
                backgroundColor: '#0f1a24',
                borderColor: '#2d3b4f',
                textStyle: {
                    color: '#b7c6da'
                }
            },
            xAxis: {
                type: 'category',
                data: data.map(d => d.label),
                axisLine: { lineStyle: { color: '#2d3b4f' } },
                axisLabel: { color: '#7b8ba3' }
            },
            yAxis: {
                type: 'value',
                splitLine: { lineStyle: { color: '#1a2634' } },
                axisLabel: { color: '#7b8ba3' }
            },
            series: [
                {
                    name: label || 'Value',
                    data: data.map(d => d.value),
                    type: 'line',
                    smooth: true,
                    showSymbol: false,
                    lineStyle: {
                        width: 3,
                        color: new graphic.LinearGradient(0, 0, 1, 0, [
                            { offset: 0, color: color },
                            { offset: 1, color: '#ffffff' }
                        ])
                    },
                    areaStyle: {
                        opacity: 0.2,
                        color: new graphic.LinearGradient(0, 0, 0, 1, [
                            { offset: 0, color: color },
                            { offset: 1, color: 'transparent' }
                        ])
                    }
                }
            ]
        };

        chart.setOption(option);

        const resizeObserver = new ResizeObserver(() => {
            chart.resize();
        });
        resizeObserver.observe(chartRef.current);

        return () => {
            resizeObserver.disconnect();
            chart.dispose();
            instanceRef.current = null;
        };
    }, [data, color, label]);

    return <div ref={chartRef} style={{ width: '100%', height }} />;
}
