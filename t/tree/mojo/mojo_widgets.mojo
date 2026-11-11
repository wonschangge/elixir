"""Module docstring mentions mojo_make_widget but is not a reference.

```mojo
struct NotARealStruct:
    var not_a_field: Int

def not_a_function():
    pass
```
"""

comptime MOJO_WIDGET_LIMIT = 3

alias MojoLabel = String

comptime MojoNever = __mlir_type.`!kgen.never`

@fieldwise_init
struct MojoWidget:
    """Struct docstring mentions mojo_make_widget."""

    var label: String

    def __init__(out self, label: String):
        self.label = label  # comment mentions mojo_make_widget

    def render(self) -> String:
        var mojo_local_only = "mojo_make_widget inside a string"
        return mojo_local_only

trait MojoWidgetLike:
    def render_like(self) -> String:
        ...

fn mojo_legacy_widget(label: String) -> MojoWidget:
    # mojo_make_widget in a comment should not count
    var mojo_fn_local = "mojo_make_widget inside a string"
    return MojoWidget(label)

def mojo_make_widget(label: String) -> MojoWidget:
    # mojo_make_widget in a comment should not count
    var text = "mojo_make_widget inside a string"
    return MojoWidget(label)

def mojo_use_widget() -> String:
    var made = mojo_make_widget("demo")
    var via = t"widget {mojo_make_widget('tmpl')}"
    return made.render()

# t/tree/mojo/mojo_widgets.mojo
# SPDX-License-Identifier: CC0-1.0
