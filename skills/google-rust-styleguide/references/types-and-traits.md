# 类型、Trait、并发与宏

对应指南章节：Types、Traits、Concurrency、Macros。

## 类型

### Newtype 与类型别名

以下情况用 newtype 而非类型别名：

- 所定义的类型有显著语义差异；
- 类型值得拥有自己的 API；
- 希望日后灵活更换底层类型，尤其当你不掌控类型的所有使用方；
- 出于类型安全，类型容易混淆时——例如 `Date` 内部计算可用 newtype 区分 `Day`、`Month`、`Year`。

### 优先命名字段

优先命名字段的类型而非元组——元组索引（`.0`、`.1`…）很快变得难以理解。例外：newtype 元组结构体（只有一个字段的 tuple struct）；极局部、不可能混淆的上下文。

## Trait

### 需要时才添加 trait 实现

一般规则：底层库代码应主动预判用户需求；应用代码按需添加 trait impl。

### 实现标准库 trait 而非自定义方法

方法的目的与行为匹配标准库 trait 时，实现该 trait：如 `Foo` 上不要写 `fn from_str(&str) -> Self`，应 `impl FromStr for Foo`。出于可发现性，方法与 trait impl 同时存在也可接受。对应 Clippy lint：`should_implement_trait`。

### 能 `#[derive()]` 就不手写

可表达为 `#[derive()]` 的实现不要手写。

### 泛型 vs `dyn Trait`

库代码函数参数优先泛型（`T: Trait` 或 `impl Trait`）而非 `dyn Trait`。例外：代码体积重要的场合。

理由：

- **效率**：`dyn Trait` 需要胖指针，每次 trait 方法调用需查 vtable；泛型函数可被内联优化，`dyn` 不行；
- 部分 trait 不兼容 `dyn`（dyn-compatible）：含泛型方法、无 self 的关联函数、返回 `Self` 的 trait。

### 何时定义 trait vs 固有实现

仅为以下目的定义 trait：

- 支持泛型编程（在泛型函数/类型的约束中使用 `T: Trait`）；
- 接受或返回 `impl Trait` / `dyn Trait`；
- 定义扩展 trait（注意扩展 trait 自身的注意事项）。

其余想为某类型实现功能的情况一律用固有实现（inherent impl）。不要用 trait 仅仅「组织代码」。

### 扩展 trait

扩展 trait（extension trait）为其他 crate 的类型添加方法；其唯一目的是加方法，不用于泛型（`T: Trait`、`impl Trait`）或动态分发（`dyn Trait`）。命名带 `~Ext` 后缀（如 `ForeignTypeExt`）。一般应由拥有原类型的团队同时拥有扩展 trait。

```rust
use foreign_crate::ForeignType;

trait ForeignTypeExt {
    fn additional_method(&self);
}

impl ForeignTypeExt for ForeignType {
    fn additional_method(&self) { /* ... */ }
}
```

也可以为「实现了某外来 trait 的每个类型」定义扩展 trait，等效于给外来 trait 加默认方法：

```rust
use foreign_crate::ForeignTrait;

trait ForeignTraitExt {
    fn additional_method(&self);
}

impl<T: ForeignTrait> ForeignTraitExt for T {
    fn additional_method(&self) { /* ... */ }
}
```

例外：预期将广为人知、价值显著的扩展方法（如基础库/框架中）可以不归原类型团队所有。

注意：此规则只针对扩展 trait。定义输入型 trait（如 `DateLike`）并实现到一批外来类型上很常见，不受此限。

理由：同一团队同时拥有扩展 trait 与被扩展类型，可避免基类型与扩展 trait 之间、或两个扩展 trait 之间的方法名冲突。

### 重要 trait 的具体指引

- **有公共字段的类型**：考虑实现所有子字段都实现的 trait。
- **错误类型**：尽可能实现 `Copy`（错误类型通常简单、按值传递更易传播）；错误必须含 `String` 之类非 Copy 字段时除外。
- **`Copy`**：能合理确定类型将来仍是 Copy 时实现。
- **`Clone`**：多数类型应实现，代表外部资源的类型除外。
- **`Default`**：类型有 `new()` 或有默认状态时实现（对应 Clippy lint：`new_without_default`）。
- **`PartialEq` / `Eq`**：想让用户用 `==` 就优先实现 `PartialEq`；实现 `Eq` 需自反性。
- **`PartialOrd` / `Ord`**：想让用户用 `<` / `>` 就优先实现 `PartialOrd`；`Ord` 要求全序。
- **Map 键**：类型可能用作 map 键或被缓存时，实现 `Hash` 与 `Eq`；另有明确全序时再实现 `Ord`。

### 重要 From impl 配套显式构造方法

某 `From` impl 是类型的主要构造途径之一时，补充固有的 `::new()`、`::new_from_foo()` 或 `::from_foo()` 方法。

### Options 结构体实现 Default

全公共字段、主要用作函数「选项包」的 struct 应实现 `Default`，以支持结构体更新语法：

```rust
Struct { a: 0, ..Default::default() }
```

## 并发

### 处理毒化（poison）

无论用例看起来多诱人，绝不伸进被毒化的 mutex 取内部数据。

### `[chrome]` 不用 async / .await

Chromium 中不使用 async / .await。

### `[chrome]` 不经标准库启动新线程

Chromium 中优先使用 sequence 而非线程。

## 宏

表达 API 时按优先级：

1. 普通 Rust 函数、类型、trait、对象与模块（尽量避免宏、代码生成与元编程）；
2. `macro_rules!` 风格宏；
3. 其他代码生成策略（如 genrule）；
4. `proc_macro` 宏。

决定用宏或代码生成时权衡成本：

- IDE、Code Search 等开发工具对宏代码支持更差；
- 宏会创造语言方言，增加跨代码库协作难度；
- 大规模变更（LSC）更难更贵。

理由：普通 Rust 代码可读性假设更强、更不易写错；`macro_rules!` 基于 AST，比文本生成稳健，适合简单代码生成。
