# 所有权、借用与 API 设计

对应指南章节：Ownership and borrowing、Function inputs and outputs（含错误报告）。

## 所有权与借用

### 避免 Rc 与 Arc

优先唯一所有权与借用管理内存，而非 `Rc`/`Arc` 共享所有权指针。

例外：当替代的所有权/借用结构在编写、理解或维护上复杂得离谱时使用——这是评审中的判断题。

理由：Rust 通常可以不用共享所有权表示对象图；引用计数有运行时开销和自身复杂度，从其他语言转来的工程师容易过早使用。

### 优先借用而非深拷贝

- 确实需要深拷贝时才用 `.clone()`；
- 不要用 `.clone()` 代替借用；设计自然契合所有权/借用规则的代码——但借用关系过于复杂时，`.clone()` 是务实的选择；
- 在 clone 与借用之间权衡性能需求；
- 注意：克隆 `Rc`/`Arc` 指针不是深拷贝，是其预期用法。

## 函数输入与输出

### 不可变数据接受最灵活的引用

传数据本身的引用，而非智能指针/容器/包装器的引用：

| 用 | 不用 | 原因 |
| --- | --- | --- |
| `&T` | `&Box<T>` | 借 box 内的数据 |
| `&[T]` | `&Vec<T>` | 接受任意切片而非特定容器 |
| `&str` | `&String` | 字符串切片而非具体 owned 串的引用 |
| `Option<&T>` | `&Option<T>` | 借 Option 内的数据 |

例外：接受 Rope/Cord 等非线性字符数据时。对应 Clippy lint：`borrowed_box`、`ptr_arg`。

### 返回类型：迭代器 vs 拥有集合

高复用库代码优先返回迭代器（具体类型或 `impl Iterator`）而非 `Vec<T>`。应用代码若返回 `Vec` 更简单、且迭代器的灵活性/性能优势用不上，返回 `Vec` 即可。

返回 `Vec` 合理的例外：多数调用者要构造 owned vector；实现天然构造 vector；返回值需要随机索引；算法用 for 循环更顺而强制分配影响不大；函数本职就是创建新集合；返回的就是已有 vector。

理由：返回迭代器让调用者自行决定 collect、循环处理或继续链式组合，可避免不必要的分配。

### 参数类型：迭代器 vs 切片

高复用库代码只需遍历输入时，接受迭代器或 `impl IntoIterator`。应用代码接受 `&[T]` 完全可以，简单为上。

理由：接受迭代器带来灵活性（任意集合）、效率（无需拷入连续内存）与组合性。

### 接受 Into

库 API 本接受 `T` 但调用者可能有多种类型时，若调用点人体工学至上，可改接受 `impl Into<T>`（如 `impl Into<String>` 可直接传 `String` 或 `&str` 字面量）。

- 与代码膨胀权衡，不必到处用 `Into<T>`；
- 应用代码几乎不应使用 `impl Into<T>` 参数。

### API 中用 enum 代替 bool

参数目的不明显时用 enum 代替 bool；若用 bool，在实参处加行内注释说明其含义：

```rust
foo(x, /* recursive= */ true)
```

## 错误报告

按 API 契约选择机制：`Option`、`Result` 或 `panic!`。

**`Option`** —— 原因显然、调用者不需要更多细节的简单失败（标准、可预期的结果，如缺值、解析不匹配）：

```rust
// Good: 失败原因显然（整数溢出），无更多细节可给
fn checked_add(a: u32, b: u32) -> Option<u32> { ... }
```

**`Result`** —— 调用者需要上下文来处理的可恢复失败；多为外部因素（I/O、网络）造成的「不可避免」错误，调用者可预期错误类别并区分处理：

```rust
// Good: 调用者需要知道 *为什么* 失败（NotFound vs PermissionDenied）
fn open_file(path: &Path) -> Result<File, io::Error> { ... }
```

**`panic!`** —— 报告 bug 与违反不变量。这类错误可通过修复代码避免，而非运行时处理：

```rust
// Good: 不变量（索引必须越界内）被违反即 panic，说明调用者逻辑有 bug
impl<T> MyVec<T> {
    pub fn remove(&mut self, index: usize) -> T {
        if index >= self.len() {
            panic!("index out of bounds");
        }
        // ...
    }
}
```

注意：有的代码库选择完全避免 panic，连不变量违反也用 `Result` 报告。

例外：面向开发者的二进制程序可对非致命错误 panic；测试中可用 panic 做断言。
