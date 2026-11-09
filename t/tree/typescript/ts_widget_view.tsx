import { ts_make_widget, TsWidget } from "./ts_widgets";

export function TsWidgetView(props: { label: string }) {
    const widget = ts_make_widget(props.label);
    return <TsWidget label={widget.render()}>ts_make_widget</TsWidget>;
}

// t/tree/typescript/ts_widget_view.tsx
// SPDX-License-Identifier: CC0-1.0
