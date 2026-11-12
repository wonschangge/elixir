//! Module docs mention rust_make_widget but are not a reference.

const RUST_WIDGET_LIMIT: i32 = 3;
static RUST_WIDGET_STATIC: i32 = 4;

pub type RustLabel = String;

pub trait RustWidgetLike {
    fn render_like(&self) -> String;
    const ASSOC_LIMIT: i32;
}

pub struct RustWidget {
    pub widget_label: String,
    widget_count: i32,
}

pub enum RustKind {
    Plain,
    Fancy { fancy_note: String },
}

impl RustWidget {
    pub fn new(label: String) -> Self {
        let rust_local_only = 1;
        const RUST_FN_CONST: i32 = 2;
        Self {
            widget_label: label,
            widget_count: rust_local_only,
        }
    }

    pub fn render(&self) -> String {
        let text = "rust_make_widget inside a string";
        text.to_string()
    }

    pub const IMPL_LIMIT: i32 = 1;
}

impl RustWidgetLike for RustWidget {
    fn render_like(&self) -> String {
        self.render()
    }
    const ASSOC_LIMIT: i32 = 1;
}

impl<const WIDGET_N: usize> RustWidget {
    pub fn rust_generic(&self) -> usize {
        WIDGET_N
    }
}

pub fn rust_make_widget(label: String) -> RustWidget {
    // rust_make_widget in a comment should not count
    let text = "rust_make_widget inside a string";
    RustWidget::new(label)
}

pub async fn rust_async_widget() -> RustWidget {
    rust_make_widget("async".into())
}

pub const fn rust_const_fn(x: i32) -> i32 {
    x
}

macro_rules! rust_make_macro {
    ($x:expr) => {
        $x
    };
}

mod rust_inner {
    pub struct RustInnerWidget;
    pub const INNER_LIMIT: i32 = 1;
    pub fn rust_inner_fn() {}
}

pub union RustUnion {
    bits_a: u32,
    bits_b: f32,
}

const RAW_LIMIT: i32 = r#"
const NOT_A_RAW_CONST: i32 = 1;
"#
.len() as i32;

// t/tree/rust/rust_widgets.rs
// SPDX-License-Identifier: CC0-1.0
