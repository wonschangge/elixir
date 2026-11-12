module {
  tt.func @mlir_use_kernel() {
    tt.call @add_kernel(%arg0) : (!tt.ptr<f32>) -> ()
    tt.return
  }
}

// t/tree/mlir/mlir_consumer.mlir
// SPDX-License-Identifier: CC0-1.0
