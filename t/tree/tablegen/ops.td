// Comment mentions TT_IntToPtrOp but is not a reference.
#ifndef TRITON_OPS
#define TRITON_OPS

include "mlir/IR/OpBase.td"

class TT_Op<string mnemonic, list<Trait> traits = []> {
  string opName = mnemonic;
}

def TT_IntToPtrOp : TT_Op<"int_to_ptr", [Pure]> {
  let summary = "Cast int64 to pointer";
  let description = [{
    def not_in_code_block : Fake;
    class NotAClass<string name> {}
    // TT_IntToPtrOp inside a code block
  }];
  let arguments = (ins I64:$src);
}

def : TT_Op<"anon">;

defm TT_MultiInst : SomeMultiClass<"inst">;

multiclass SomeMultiClass<string n> {
  def _reg : TT_Op<n>;
}

defvar GenericSharedRead = [MemRead];
defvar WidgetAlias = TT_IntToPtrOp;

defset list<int> WidgetSet = {
  def SetItem : TT_Op<"set">;
}

deftype WidgetInt = i32;

let isTerminator = 1 in {
  def TT_ReturnOp : TT_Op<"return">;
}

foreach i = [1, 2] in {
  def PastedName#i : TT_Op<"x">;
}

def TT_StringMention : TT_Op<"str"> {
  let summary = "TT_IntToPtrOp inside a string";
}

#endif

// t/tree/tablegen/ops.td
// SPDX-License-Identifier: CC0-1.0
