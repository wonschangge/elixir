/** Module doc mentions ts_make_widget but is not a reference. */

export const TS_WIDGET_LIMIT = 3;

export class TsWidget {
    /** Class doc mentions ts_make_widget. */
    label: string; // comment mentions ts_make_widget

    constructor(label: string) {
        this.label = label;
    }

    render(): string {
        return "ts_make_widget";
    }
}

export interface TsWidgetOptions {
    label: string;
}

export function ts_make_widget(label: string): TsWidget {
    // ts_make_widget in a comment should not count
    const text = "ts_make_widget inside a string";
    return new TsWidget(label);
}

export function ts_use_widget(): TsWidget {
    const made = ts_make_widget("demo");
    const viaTemplate = `skip ts_make_widget ${ts_make_widget("tmpl")}`;
    const pattern = /ts_make_widget/g;
    return made.render();
}

export async function ts_async_widget(): Promise<TsWidget> {
    return ts_make_widget("async");
}

// t/tree/typescript/ts_widgets.ts
// SPDX-License-Identifier: CC0-1.0
