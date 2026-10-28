# 实现细节

对应指南章节：Implementation concerns。

## 别滥用类型推断

加足够的显式类型，让熟悉代码库的人能推断出被推断的类型是什么。优先在变量声明处标类型，而非 turbofish（`::<_>`）；编译器逼你写 turbofish 时，一般加 `_` 推断标记即可。

特别应加类型的情形：

- 调用泛型返回值的方法，如 `.into()`、`.parse()`；
- 复杂迭代器链的结果。

## 优先模式匹配而非先检查再 unwrap

当输入数据保证不会 panic 时，避免潜在 panic 的操作。例如值已确定有效时，不要 `Option::unwrap`，用模式匹配向编译器证明正确性：

```rust
// Good: match 臂向编译器证明 `x` 是 `Some`，panic 明显不可能
if let Some(value) = option {
    use_value(value);
}

// Bad: unwrap 的正确性依赖运行时检查 option 是 Some
if option.is_some() {
    use_value(option.unwrap());
}
```

## 优先 expect 而非 unwrap

不变量无法用类型系统表达、必须 panic 时，用 `expect` 代替 `unwrap` 以说明原因。

## 匹配 non_exhaustive enum 时不要省略变体

优先在 match 中列出全部 enum 变体。不关心的变体放进通配臂；只关心个别变体时用 `if let` 或 `let ... else`。

```rust
#[non_exhaustive]
pub enum Shape {
    Circle,
    Square,
    Triangle,
}

fn process_shape(shape: Shape) {
    match shape {
        Shape::Circle => println!("It's a circle"),
        Shape::Square => println!("It's a square"),
        // Triangle 与未来变体无需处理
        Shape::Triangle | _ => {}
    }
}

fn process_shape(shape: Shape) {
    if let Shape::Circle = shape {
        println!("It's a circle");
    }
}
```

例外：只关心个别变体、且 match 比 `if let` 更整洁时。

## 用上下文字符串澄清断言

`assert!` 利用可选格式串参数补充上下文：说明断言为何应成立、或什么导致了违反。应考虑加上下文，尤其在：

- 想给断言加注释时——改用格式串，它会出现在日志里；
- 失败断言会被用户看到时——人话解释比 Rust 表达式更有用；
- 记录某个值有助于理解失败原因时；
- 需要区分失败含义——是客户端误用 API（应改用法），还是实现有 bug（应报 bug）。

```rust
// 解释断言为何应成立
assert!(
    values.is_sorted(),
    "`values` is populated from a `PriorityQueue`, so we expect it to be sorted"
);

// 记录值以澄清失败原因
assert!(refund > 0, "Refund must be positive, got {refund:?}");

// 标记 API 误用
fn execute_query(&self, query: &str) {
    assert!(self.stream.is_some(), "Call connect() before executing queries");
}
```

不要用上下文字符串单纯复述条件：

```rust
// Bad: 只是重复条件
assert!(values.is_sorted(), "values should always be sorted");
```

## 组合子链影响可读性时改用直接迭代

- 避免又长又复杂的组合子链；
- 不要在 for 循环头部构造组合子链——先赋给变量，再在循环中消费（变量名还能说明链的用途）；
- 避免用 `Iterator::for_each`，除非确有理由；for 循环通常更易读。

组合子更适合短链、或组合子本身承载大量逻辑（否则要在 for 循环里展开写）的场合。

```rust
// Bad: 复杂组合子链（含条件与外部状态变更）
let mut error_count = 0;
let _processed_items: Vec<_> = items
    .into_iter()
    .map(transformation_that_may_fail)
    .map(|result| {
        if result.is_err() {
            error_count += 1;
        }
        result
    })
    .filter_map(Result::ok)
    .collect();

// Good: 对应的 for 循环更易读
let mut error_count = 0;
let mut processed_items = Vec::with_capacity(items.len());

for item in items {
    match transformation_that_may_fail(item) {
        Ok(val) => processed_items.push(val),
        Err(_) => error_count += 1,
    }
}
```

```rust
// Bad: for 循环头部构造组合子链
for bug in bug_descriptions
    .iter()
    .filter_map(|description| parse_bug_description(description).ok())
    .filter(|bug| bug.priority <= Priority::P1)
{
    assign_bug(bug);
}

// Good: 先赋给变量
let urgent_bugs = bug_descriptions
    .iter()
    .filter_map(|description| parse_bug_description(description).ok())
    .filter(|bug| bug.priority <= Priority::P1);

for bug in urgent_bugs {
    assign_bug(bug);
}
```

```rust
// Good: 组合子更优的例子——any() 复用逻辑，for 循环反而更啰嗦
let threshold_exceeded = values.iter().any(|&v| v > threshold);
```

## 禁用 `panic::catch_unwind`

第一方 Rust 代码禁止调用 `panic::catch_unwind`。

例外：作为纵深防御机制可以接受——前提是绝不依赖它提供任何性质。已经在尽力避免 panic 的代码库，可以选择在关键入口包一层恢复机制以防 panic 漏网；作者须说服评审代码库已在尽力避免 panic。该例外只适用于可能以 `panic=unwind` 运行的代码（Chrome/Android/Fuchsia 均要求 `panic=abort`，不适用）。

理由：`panic::catch_unwind` 只在 `panic=unwind` 环境下正确工作，而 Rust 代码可能被用于多种环境。

## 字符串拼接与替换用 format! / write!

以下情况优先 `format!()` 与 `write!()`：

- 拼接超过两个字符串：用 `format!("{a}{b}{c}")` 而非 `a + b + c`；
- 对字面量字符串做替换：用标准格式串，不要发明自己的模板语法，也优于 `str::replace`。

理由：`format!` / `write!` 的分配次数少于 `+` 拼接。

## 使用代码库指定的测试框架

多数代码库使用自己的测试框架而非 `#[test]`：

- Chrome：用 `rust_gtest_interop`，使 Rust 测试可集成进 C++ 测试二进制；
- Fuchsia：用 `#[fuchsia::test]`。
