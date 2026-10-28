# 命名与文档

对应指南章节：Naming、When and how to write documentation。

## 命名

### 方法命名

遵循 Rust 标准库风格。使用 `as_...()`、`to_...()`、`into_...()` 前缀并配对正确的 self 约定（参考 Rust API Guidelines 的命名约定与 Clippy lint `wrong_self_convention`）。

### 生命周期命名

生命周期应有描述性名称，类型的生命周期尤其如此。例外：

- 极泛化的抽象（如 `Cow`）；
- 能用时可用匿名生命周期（`'_`）；
- 单字母生命周期仅用于表达方法输入输出关系、或局部 higher-ranked 约束（`for<'a>`）时可以；最多两个，再多强烈建议用描述性名称。

### 泛型参数命名

用与所代表事物相关的短名（单字母或多字符）。单字母可以，但字母最好暗示对象类型，理想情况取自最重要的 trait bound。`T`、`U` 可用于较不受限的上下文（如 `Vec<T>` 这类面向大多数类型的 API）。

### 扩展 trait 命名

带 `~Ext` 后缀（如 `ForeignTypeExt`）。

### 初始化函数命名

- 构造器：`new()`；多个时 `new_with_foo()`；返回 `Result` 的构造器用 `try_new()`。
- 值到值转换：`from_foo()`，并配关联的 `From` impl。

### 避免缩写

不用项目外的人不认识的缩写（尤其首字母缩略词与 initialism）；不要删词中字母来缩写。例外：Wikipedia 上的常见缩写；项目外的人不太可能困惑的缩写（如 `IpAddr`），由作者与评审判断——总体倾向仍是不缩写。

## 文档

### 何时写

- 公共 API 添加文档注释；可用 `missing_docs` lint 辅助。
- 考虑包含示例：不必每个函数都有示例，但 crate 的用法应被示例充分覆盖。
- 可能因输入不合法而 panic 的函数，必须文档化 panic 行为。
- unsafe 函数与 trait 的不变量必须清晰文档化。
- 使用大写与标点。
- 不解释编程语言基础。例如不要写：

  ```rust
  struct MockFileSystem { ... }

  /// A mock implementation of the FileSystem trait, intended to be used in unit tests.
  impl FileSystem for MockFileSystem
  ```

例外：

- 注释应说出代码本身说不出的信息；没有可说的内容时，宁可省略注释，也不要用琐碎方式复述函数名（这种情况下允许放行 missing_docs lint）：
  ```rust
  /// Removes an element.
  pub fn remove_element() -> Element {}
  ```
- 单个 enum 变体的文档一般可省略，尤其名字自解释时。

### 如何格式化

- 用 `///` 文档其后紧跟的条目：函数、struct、enum、trait、类型别名。
- 用 `//!` 文档模块或库本身，置于文件顶部。
- 遵循官方 Rust style guide 的 doc comment 规则；使用 Markdown 语法。
- 非文档注释（实现说明、对用户无趣的 TODO、注释掉的代码等）用普通 `//`。
- 优先直接用 `///` / `//!` 书写文档，而非从宏生成——源码中可直接阅读。
- 文档注释与普通注释可以且鼓励混用：

  ```rust
  /// Finds the first `FooItem` with the given `name`, or `None` if not present.
  // TODO: crbug.com/12345 - `name` should be &str, not String.
  pub fn get_named(items: &[FooItem], name: String) -> Option<&FooItem> {...}
  ```

理由：`///` 与 `//!` 可被 rustdoc、IDE、Kythe 等工具消费；有标准结构（Markdown）支持富文本；语法错误会被 lint 捕获，无 lint 错误即保证文档对工具可见；doc comment 属于 AST，可由宏产出与消费。
