# 其他 Rust 特性

对应指南章节：Other Rust features。

## Unsafe 代码

除非安全代码无法实现同样功能，否则不写 unsafe 代码。

必须写 unsafe 时：

1. **封装为安全抽象**，与业务逻辑尽量隔离；理想情况下 unsafe 代码放在依赖极少（仅标准库）的独立 crate 中。
2. **加 `SAFETY:` 注释**，解释代码为何正确：
   ```rust
   // SAFETY: `p` 指向的有效内存由调用方契约保证……
   unsafe { ... }
   ```
3. **给出技术论证**：可以针对单个 unsafe block，也可以覆盖整个文件或构建目标。论证应回答：
   - 为什么这段代码不用等价的安全方式写？
   - 若理由是性能，有 benchmark 吗？

## 不用不稳定特性

禁止使用 nightly-only 的不稳定（unstable）特性。例外（按代码库）：

- Android 嵌入式编程可能必需某些不稳定特性；需评审放行（帮助寻找替代），构建产物绝对必需的特性一般会批准。
- Chrome：风格仲裁者可为整个代码库统一批准一个小清单，通常只批准有明确稳定路径的特性。
- Fuchsia：见其专属指引。

## Getter 与 setter

| 方法 | 行为 |
| --- | --- |
| `foo()` | getter，返回 `&T`；`T: Copy` 时按值返回 `T` |
| `foo_mut()` | getter，返回 `&mut T` |
| `take_foo()` | 把值「清空」（置 `None` 或其他默认态）并返回旧值 |
| `set_foo()` | setter，按值接收 `T` |
| `with_foo()` / `with_mut_foo()` | 经闭包访问：`object.with_foo(\|foo\| frob(foo))` |
| `replace_foo()` | setter，返回旧值 |

```rust
impl Stuff {
    fn foo(&self) -> &Foo { /* ... */ }
    fn foo_mut(&mut self) -> &mut Foo { /* ... */ }

    /// 将 "baz" 属性置为 `None`，返回旧值。
    fn take_baz(&mut self) -> Option<Baz> { /* ... */ }

    fn set_foo(&mut self, foo: Foo) { /* ... */ }

    /// 用 "bar" 属性的可变借用调用 `f`，返回 `f` 的返回值。
    fn with_mut_bar<R>(&self, f: impl FnOnce(&mut Bar) -> R) -> R { /* ... */ }

    /// 将 "foo" 属性设为 `foo`，返回旧值。
    fn replace_foo(&mut self, foo: Foo) -> Foo { /* ... */ }
}
```

### 闭包访问器的适用场景

`with_foo()` 通常这样调用：`object.with_foo(|foo| do_something_with(foo))`。适合的场景：

- 属性在内可变性包装器（`Mutex`、`RefCell`）中：闭包把访问约束在一个作用域内，通常优于直接返回 RAII guard（如 `MutexGuard<T>`，会泄漏实现细节）；
- 属性变更后需要后续处理或校验、而 `set_foo()` 用不了（属性类型 clone 昂贵或不可 clone）时。

`with_foo()` 常让闭包有返回值并由其转发。同时提供只读与可变两个闭包访问器时，命名为 `with_foo()` / `with_mut_foo()`；否则 `with_foo()` 也常用于可变访问。

## 成套实现预期 API 集

实现了 `len()` 就应实现 `is_empty()`（Clippy lint：`len_without_is_empty`）。

## 不访问不属于自己的 `#[doc(hidden)]` 条目

把 `#[doc(hidden)]` 条目当作私有对待；不拥有该代码就不要访问。

## 负责任地使用 const 函数

只在预期函数将来保持 const（或承诺在变更时协助客户迁移）时，才把公共函数标为 `const`。

理由：把 `const fn` 改回普通函数是破坏性变更。

## 运算符重载只用于数学/逻辑本义

运算符重载只用于其原始的数学/逻辑用途，不要只为代码简短当「语法糖」。

## 公共 enum 加 `#[non_exhaustive]`

enum 属于跨团队使用的公共 API 时，标记 `#[non_exhaustive]`。例外：

- enum 永远不会变：描述既有本体（如 `enum Color { Red, Green, Blue }`）；或两态、等价布尔（如 `enum Visibility { Visible, Hidden }`）；
- 将来会变，但已承诺通过 LSC 修复下游破坏。

理由：`#[non_exhaustive]` 迫使用户在 match 中写通配臂（`_ => ...`），保证日后新增变体时代码仍能编译。跨团队边界的 enum 破坏面大，必须遵守；仅少量使用的 enum 影响有限，可忽略此规则。（Clippy lint：`exhaustive_enums`）

## 全公共字段 struct 加 `#[non_exhaustive]`

跨团队公共 API 中、字段全公共的 struct 应标 `#[non_exhaustive]`。例外：

- 字段不太可能变（如描述既有本体的 `Rectangle`），或评审有信心不会变；
- 会变，但已承诺用 LSC 修复破坏；
- 想让用户能用函数式记录更新语法（FRU）：`Person { name: "foo", ..Default::default() }`。

理由：给全公共字段的 struct 新增字段（哪怕私有字段）是破坏性变更——调用者无法再完整写出 struct 字面量。`#[non_exhaustive]` 的 struct 禁止 crate 外用字面量构造，从而允许新增私有字段。

## `#[must_use]` 标注函数

以下情况给函数加 `#[must_use]`：

- 调用者忽略返回值就无法正确使用该函数，包括无副作用的纯函数（如 `HashMap::get()`）；
- 返回值代表错误或行为关键信息的函数。返回类型已标 `#[must_use]`（如 `Result`）时，函数不必再标。

## `#[must_use]` 标注类型

给「按上述规则本会标 `#[must_use]` 的函数」所返回的类型加 `#[must_use]`。示例：

- 类型是错误类型（类似 `Result` 或 `StatusOr`）；
- 类型代表惰性求值的计算——函数调用本身不做任何事，必须访问返回值才产生预期副作用。

## 不在 `main()` 前运行代码

不要让代码在 `main()` 之前执行，例如不要使用 `ctor` crate 之类技术。
