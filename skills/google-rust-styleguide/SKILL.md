---
name: google-rust-styleguide
description: 按 Google Rust 风格指南编写、修改与评审 Rust 代码。当用户要求写 Rust 代码、评审 Rust PR/diff、创建 Rust crate/模块、设计 Rust API、配置 rustfmt/clippy，或明确提到 "Google Rust style guide"、"Rust 风格"、"Rust 规范" 时使用本 skill。涵盖代码组织、导入规则、所有权与 API 设计、类型与 trait、命名、文档注释、unsafe、实现细节等主题。
license: CC-BY-2.5
metadata:
  version: "1.0.0"
  upstream: https://google.github.io/styleguide/rustguide.html
---

# Google Rust 风格指南

本 skill 是 Google Rust Style Guide（https://google.github.io/styleguide/rustguide.html）的操作版摘要。编写或评审 Rust 代码时遵循这些规则；"style" 不只是格式，还包括 API 设计与实现设计。

## 何时使用

- 编写、修改、重构 Rust 代码（`.rs` 文件、crate、模块）
- 评审 Rust 代码 / PR / diff
- 设计 Rust 库或应用的 API（函数签名、类型、trait、错误处理）
- 配置 rustfmt / 讨论 Rust 风格分歧

## 如何使用

1. 先通读下方「核心原则」与「规则速览」；
2. 涉及某主题细节时，按索引表读取对应 `references/` 文件（按需加载，不必全读）；
3. 写代码时直接应用规则；评审时按主题逐条对照。

## 核心原则

1. **遵循公开的 Rust 风格规则**：官方 Rust Style Guide 与 Rust API Guidelines 在不冲突时仍然适用；格式由 rustfmt 自动执行。
2. **可读性与可维护性优先于可写性**：代码要长期存活，写时多花一点成本换长期可读是值得的。
3. **利于自动化与大规模重构（LSC）**：选择工具容易处理、重构友好的模式，保持一致。
4. **与 Rust 生态惯例保持一致**：减少意外，降低学习成本。
5. **区分库代码与应用代码**：API 设计规则对库代码是强制的；对应用代码是强建议——应用代码应简单直接，避免过早泛化抽象。
6. **规则要有实际收益**：避免为风格而风格的规则。

## 规则速览

### 代码组织与导入（详见 references/code-organization.md）

- 优先小而聚焦的 crate；单 crate 的 `.rs` 源文件放在同一目录，不用子目录组织（Chromium 规则，其他代码库酌情）。
- 非叶子模块只放模块声明与 re-export，不放 API 实现。
- 禁止 glob 导入（`use foo::*`），例外：`super::*`、enum 处理、非叶子模块 re-export。
- 一条 `use` 只从一个模块导入（`imports_granularity = Module`），花括号内不出现 `::`。
- trait 尽量在函数体内局部导入；类型按名直接使用（`Regex`，不是 `regex::Regex`）；顶层函数调用带模块名限定（`mem::transmute(y)`）。

### 格式化（详见 references/code-organization.md）

- 用 rustfmt（或代码库指定的格式化工具）自动格式化；推荐 `max_width = 100`、`hex_literal_case = "Lower"`、`format_macro_matchers = true`。
- 仅在手工对齐、生成代码两种情况下可用 `#[rustfmt::skip]`；不得为个人风格跳过格式化。

### 所有权、借用与 API 设计（详见 references/ownership-and-apis.md）

- 避免 `Rc`/`Arc`，除非共享所有权确实显著简化代码；优先借用而非 `.clone()` 深拷贝。
- 不可变入参用最灵活的引用：`&T` 而非 `&Box<T>`、`&[T]` 而非 `&Vec<T>`、`&str` 而非 `&String`、`Option<&T>` 而非 `&Option<T>`。
- 库代码返回迭代器 / `impl Iterator` 优于 `Vec<T>`；只遍历的入参接受 `impl IntoIterator`。应用代码可以为了简单直接用 `Vec`/`&[T]`。
- 用 `enum` 代替含义不明的 `bool` 参数；`Option`（显然的失败）、`Result`（需上下文的可恢复错误）、`panic!`（bug 与不变量违反）各司其职。

### 类型与 trait（详见 references/types-and-traits.md）

- 有语义差异、需要独立 API、类型易混淆时用 newtype 而非类型别名；优先命名字段结构体。
- 能用 `#[derive()]` 就不手写 impl；行为匹配标准库 trait 就实现该 trait 而非自定义方法。
- 库代码优先泛型（`T: Trait` / `impl Trait`）而非 `dyn Trait`。
- 只为泛型编程、`impl/dyn Trait`、扩展 trait 定义 trait；不要用 trait「整理代码」。
- 扩展 trait 命名带 `Ext` 后缀（如 `ForeignTypeExt`）；`From` impl 是主要构造途径时配套固有 `::new_from_foo()`；选项结构体实现 `Default`。

### 并发与宏（详见 references/types-and-traits.md）

- 绝不解开毒化（poisoned）的 mutex 去取内部数据。
- 宏优先级：普通 Rust 代码 > `macro_rules!` > 代码生成 > `proc_macro`；能不用宏就不用。

### 命名与文档（详见 references/naming-and-docs.md）

- 方法命名遵循标准库惯例（`as_`/`to_`/`into_`、getter `foo()`/`foo_mut()`、setter `set_foo()`、`take_foo()`/`replace_foo()`、`with_foo()` 闭包访问器）。
- 生命周期与泛型参数用有描述性的短名；避免项目外的人看不懂的缩写。
- 公共 API 写文档注释：`///` 用于条目，`//!` 用于模块；文档 panic 行为与 unsafe 不变量；注释要说代码说不出来的事。

### 其他语言特性（详见 references/language-features.md）

- 能用安全代码就不用 `unsafe`；unsafe 必须封装为安全抽象并带 `SAFETY:` 注释与技术论证。
- 不用不稳定（nightly-only）特性。
- 跨团队公共 enum / 全公共字段 struct 加 `#[non_exhaustive]`；`#[must_use]` 标注忽略返回值即错的函数与类型。
- 公共 `const fn` 谨慎标注（改回普通函数是破坏性变更）；运算符重载只用于数学/逻辑本义；不在 `main()` 前跑代码。

### 实现细节（详见 references/implementation-concerns.md)

- 别滥用类型推断；`.into()`/`.parse()`/复杂迭代器链的结果要显式标注类型。
- 用模式匹配代替 is_some()-then-unwrap；必须 panic 时用 `expect` 说明原因；`assert!` 附上下文格式串。
- 迭代器组合子链别太长太复杂；for 循环头里别构造组合子链；简单判断用 `any()` 等组合子更清晰。
- 禁用 `panic::catch_unwind`（纵深防御除外）；拼 3 个以上字符串或做字面量替换用 `format!`/`write!`。

## 参考文件索引

| 主题 | 文件 | 内容 |
| --- | --- | --- |
| 代码组织、导入、格式化 | references/code-organization.md | crate/模块布局、glob 与 use 规则、rustfmt 配置与 skip |
| 所有权、借用、函数输入输出、错误报告 | references/ownership-and-apis.md | Rc/Arc、clone、引用选择、迭代器 vs Vec、Into、enum vs bool、Option/Result/panic |
| 类型、trait、并发、宏 | references/types-and-traits.md | newtype、derive、泛型 vs dyn、扩展 trait、重要 trait、毒锁、宏优先级 |
| 命名与文档 | references/naming-and-docs.md | 方法/生命周期/泛型命名、Ext 后缀、初始化函数、缩写、文档注释写法 |
| 其他语言特性 | references/language-features.md | unsafe、不稳定特性、getter/setter、non_exhaustive、must_use、const fn、运算符 |
| 实现细节 | references/implementation-concerns.md | 类型推断、模式匹配、expect、assert 上下文、组合子链、catch_unwind、format!、测试框架 |

## 评审对照清单（快速版）

评审 Rust 代码时按此顺序快速过一遍：

1. rustfmt/clippy 是否通过？格式分歧不要在评审中反复讨论，交给工具。
2. 导入：有无 glob 导入？use 粒度是否符合一个模块一条？
3. API：引用类型是否选了最灵活的？bool 参数是否该改 enum？错误是否选对 Option/Result/panic？
4. trait：是否该用标准库 trait？扩展 trait 是否带 `Ext`？
5. 实现：unwrap 前是否该用模式匹配？assert 有无上下文？组合子链是否影响可读性？
6. unsafe：有无 `SAFETY:` 注释与论证？能否用安全代码替代？
