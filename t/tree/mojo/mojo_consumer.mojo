"""Consumer calls mojo_make_widget only in real code."""

from mojo_widgets import mojo_make_widget

def mojo_consume(label: String):
    return mojo_make_widget(label)

# t/tree/mojo/mojo_consumer.mojo
# SPDX-License-Identifier: CC0-1.0
