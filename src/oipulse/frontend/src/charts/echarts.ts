/**
 * Tree-shaken ECharts core. Import the registered `echarts` from here, never
 * from 'echarts' directly — that pulls the full ~1MB bundle. We register only
 * the chart types + components OI Pulse actually uses, keeping the charts chunk
 * around ~300KB. Add a component here when a new chart needs it.
 */

import * as echarts from 'echarts/core'
import { BarChart, LineChart, HeatmapChart, ScatterChart, CustomChart, GaugeChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
  MarkLineComponent,
  MarkPointComponent,
  VisualMapComponent,
  AxisPointerComponent,
  TitleComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { ComposeOption } from 'echarts/core'
import type {
  BarSeriesOption,
  LineSeriesOption,
  HeatmapSeriesOption,
  GaugeSeriesOption,
  ScatterSeriesOption,
  CustomSeriesOption,
} from 'echarts/charts'
import type {
  GridComponentOption,
  TooltipComponentOption,
  LegendComponentOption,
  DataZoomComponentOption,
  VisualMapComponentOption,
} from 'echarts/components'

echarts.use([
  BarChart,
  LineChart,
  HeatmapChart,
  ScatterChart,
  CustomChart,
  GaugeChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
  MarkLineComponent,
  MarkPointComponent,
  VisualMapComponent,
  AxisPointerComponent,
  TitleComponent,
  CanvasRenderer,
])

export type EChartsOption = ComposeOption<
  | BarSeriesOption
  | LineSeriesOption
  | HeatmapSeriesOption
  | GaugeSeriesOption
  | ScatterSeriesOption
  | CustomSeriesOption
  | GridComponentOption
  | TooltipComponentOption
  | LegendComponentOption
  | DataZoomComponentOption
  | VisualMapComponentOption
>

export { echarts }
