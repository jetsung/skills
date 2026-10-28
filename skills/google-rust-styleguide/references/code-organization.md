# 代码组织、导入与格式化

对应指南章节：Code organization、Code formatting and aesthetics。

## 代码组织

术语：crate 是编译单元，含一个无名的根模块；module 是 crate 内的代码组织单元，控制可见性、可嵌套、可跨文件拆分。

### 优先小 crate `[chrome]`

Chromium 中优先小 crate，理想情况下单个文件、聚焦一个抽象。能拆就拆。

- 根模块可以 re-export 叶子子模块的公共 API，使子模块成为 crate 的实现细节。
- 先评估这些 API 是否需要同处一个 crate，再考虑子模块；该规则对有/无子模块的 crate 同样适用。
- 大 crate 仅在 trait 一致性（coherence）迫使多类型/ trait 同库，或构建大型基础库时允许。
- 理由：巨型代码库中，依赖图的非局部影响、并行编译与构建缓存收益。

### 单 crate 源文件扁平布局 `[chrome]`

一个 `rust_library`（一个 crate）的 `.rs` 文件必须放在同一目录；不用子目录组织。若感觉需要子目录，说明 crate 太大应拆分。例外：`//third_party` 中同时用 Cargo 构建的代码遵循常规 Cargo 目录结构。

### 源文件与叶子模块以主条目命名

叶子模块有主要类型（如 `Foo`）时，模块名对应该条目（`mod foo`、`foo.rs`）；不围绕某个抽象的叶子模块可自由命名。

### 非叶子模块不放 API 实现

非叶子模块只应有模块声明（而非定义）与 re-export。例外：少量把各部分「串起来」的核心代码可以放在非叶子模块；`mod test` 与 `#[cxx::bridge]` 等跨语言绑定模块不算违反。

### 禁止 glob 导入

不用 `use foo::*`，以下情况可自行斟酌：

- 内联模块中的 `use super::*`；
- enum 的方法体内、以及主要处理该 enum 的函数中的 `use enum::*`；
- 非叶子模块的 `pub use submodule::*`；
- C++ 互操作：同一 C++ 命名空间散布在不同 Rust crate 的子模块时，可合并进一个私有模块：
  ```rust
  mod absl {
      pub use status::absl::*;
      pub use strings::absl::*;
  }
  ```
  仅限合并 C++ 命名空间，且合并后的模块不得公开。
- 第三方 crate 的 prelude 是否可用由评审裁量；同样避免自定义 prelude。

理由：glob 导入加大 LSC 工具的负担，且在无交叉引用的上下文里难以判断类型来源。

### 一条 use 语句只导入一个模块

对应 rustfmt 设置 `imports_granularity = "Module"`；`{..}` 内不应出现 `::`：

```rust
// Good
use foo::Foo;
use foo::bar::{Bar, Baz};

// Bad
use foo::{Foo, bar::Bar};
```

### trait 尽量局部导入

除非 trait 方法在文件中大量使用，否则在函数体内导入：

```rust
fn foo(s: &str) -> Result<u8, std::num::ParseIntError> {
    use std::str::FromStr; // 函数内导入，不放模块级
    u8::from_str(s)
}
```

### 顶层函数调用带模块名限定

```rust
use std::mem;
let x = mem::transmute(y); // Good
```

```rust
use std::mem::transmute;
let x = transmute(y); // Bad
```

例外：函数名本身已充分消歧（如 C++ 函数）；来自小型单一用途的第一方 crate 的函数（Chromium）；模块名本身易冲突（如与 C++ 命名空间同名）时。

### 类型名不加路径直接使用

代码应写 `Regex` 而非 `regex::Regex`，文件顶部（或相关函数内）`use regex::Regex;`。例外：`io::Error` 这类常见歧义名（或 `use std::io::Error as IoError;`）；`rustc` 的 `hir` 这类大型类型组；宏与生成代码；依赖极多、全量导入得不偿失的场景。

## 格式化

### 使用对应代码库的格式化工具

格式分歧交给工具（如 Chromium 的 `git cl format`），不在评审中反复讨论。

**样式指南作者可参考的 rustfmt 配置**（若关注在 stable 构建、而选项在 stable 不可用，可不启用）：

```toml
max_width = 100                 # 每行最多 100 列
hex_literal_case = "Lower"      # 十六进制字面量小写：0xab123cdef
format_macro_matchers = true    # 宏 matcher 格式化
```

不可见字符用转义：如零宽连接符写 `\u{200D}`。

### 退出自动格式化的唯一方式：`#[rustfmt::skip]`

仅允许两种情况：

1. **手工对齐**——有场景性理由让代码按特定方式对齐（如多行相似代码保持对齐、构造矩阵的函数）；
2. **生成代码**（理想情况下改用 genrule）。

重要：不得为个人风格偏好跳过格式化。
