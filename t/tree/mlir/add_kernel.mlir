// Module comment mentions add_kernel but is not a reference.
// tt.func @not_a_comment_def

#BlockedLayout = #ttg.blocked<{sizePerThread = [1], threadsPerWarp = [32], warpsPerCTA = [1], order = [0]}>
!widget_tensor = type tensor<16xf32, #BlockedLayout>

module {
  tt.func public @add_kernel(%arg0: !tt.ptr<f32>, %arg1: i32) {
    %0 = tt.get_program_id x : i32
    %c256_i32 = arith.constant 256 : i32
    %1 = arith.muli %0, %c256_i32 : i32
    // add_kernel in a comment should not count
    %text = "add_kernel inside a string"
    tt.call @add_kernel(%arg0) : (!tt.ptr<f32>) -> ()
    tt.return
  }

  llvm.func @llvm_helper(%arg0: i32) -> i32
  llvm.mlir.global external @global_smem() {addr_space = 3 : i32} : i8
  llvm.call @llvm_helper(%arg0) : (i32) -> i32
  %ptr = llvm.mlir.addressof @global_smem : !llvm.ptr<3>

  func.func private @private_fn(%arg0: i32) {
    %0 = arith.constant 1 : i32
    return
  }

  module @named_module {
    gpu.func @gpu_kernel() kernel {
      gpu.return
    }
  }
}

"func.func"() <{sym_name = "generic_fn", function_type = () -> ()}> {
  "func.return"() : () -> ()
}

irdl.dialect @demo_dialect {
  irdl.type @demo_type {}
  irdl.attribute @demo_attr {}
  irdl.operation @demo_op {}
}

// t/tree/mlir/add_kernel.mlir
// SPDX-License-Identifier: CC0-1.0
