<!-- auto-generated from https://raw.githubusercontent.com/casey/just/refs/heads/master/README.md — compact AI knowledge, not verbatim -->
<!-- update: python3 scripts/update.py — regenerates this compact file -->
<!-- book: https://just.systems/man/en/ | src: https://raw.githubusercontent.com/casey/just/refs/heads/master/README.md -->
# just — compact knowledge (AI-only, non-human-readable)

## 0 meta
ver>=1.0 promises no 2.0 (opt-in breaking); unstable requires `set unstable`|`--unstable`|`JUST_UNSTABLE`; `set minimum-version:="x.y.z"` gates; MSRV=stable Rust.

## 1 install & compat
compat: any POSIX `sh`; Windows needs Git-for-Windows/Cygwin `sh` or `set shell:=["powershell.exe","-c"]`/`["cmd.exe","/c"]`; `--shell`/`--shell-arg` CLI.
install: `cargo install just`|`cargo binstall just`|`brew install just`|`apt/dnf/pacman/apk install just`|`nix-env -iA nixpkgs.just`|`conda install -c conda-forge just`|`npm i -g rust-just`|`pipx/uv tool install rust-just`|`arkade/asdf/snap` | releases `https://github.com/casey/just/releases` | `curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash -s -- --to DEST` (rate-limited, use `--tag` or `GITHUB_TOKEN`) | Docker `COPY --from=ghcr.io/casey/just:latest /just /usr/local/bin/` | GHA `extractions/setup-just@v3`/`taiki-e/install-action@just` | Node `just-install` | Nix flake `just.url="github:casey/just"`.

## 2 file discovery & invocation
search: cwd upward for `justfile`/`.justfile` case-insensitive; `just` with no args runs `[default]` else first recipe; `just a b c` sequential deps-first; `just foo/build` ≡ `(cd foo && just build)`; `just foo/` ≡ `(cd foo && just)`; `--justfile <p>` (`-` stdin, `.md` extracts unindented ```just), `--working-directory <d>`, `--global-justfile`/`-g` searches `$XDG_CONFIG_HOME/just/justfile`→`~/.config/just/justfile`→`~/justfile`→`~/.justfile`; Markdown justfile extracts ```just; shebang `#!/usr/bin/env just --justfile` (`env -S` on Linux), `--working-directory .` to keep cwd.

## 3 recipe
syntax: ` [attrs] name [params]: [deps] ` + indented body lines each executed as `sh -cu 'line'` (or `set shell`); body lines: `@` no-echo, `-` ignore-error, `?` guard (requires `set guards`), combos `@-`; `#` comment; `# doc` immediately preceding recipe shows in `--list` (or `[doc("...")]`/`[doc]` suppress); `{{expr}}` interpolation in body/deps/attr-args; `{{{{`→`{{`, unmatched `}}` ignored; indentation canonical 4sp, `set indentation:="  "`/`JUST_INDENTATION`/`--indentation`, `--fmt` formats, `--fmt --check` checks, `--dump` dumps formatted, `--dump --dump-format json` JSON.
default: `[default]` else first; `set default-list:=true` lists; example `default: lint build test`.

## 4 params
forms: `name` required, `name="default"` optional (default may be any expr, parenthesize if contains `+`/`&&`/`||`/`/`), `*name` zero-or-more variadic, `+name` one-or-more variadic (both expand to space-joined string, or list if `set lists`), `+name="def"` variadic default overridden by CLI; `$name` exported env var; param passed as `just recipe arg1 arg2`; dep invocation `(build "main")`|`(build target)`|`(_build target)`; variadic may have `min`/`max` via `[arg]`.
quoting pitfalls: `{{arg}}` splits on spaces; fix via `'{{arg}}'` (fails if `'` present), `touch "$1"` with `set positional-arguments` (see §5), or `set export`/`$arg` + `"$arg"`.
arg attrs (>=1.45): `[arg("name", pattern="REGEX")]` anchored `^$`, Rust regex, `|` alternatives, const expr >=1.55; `[arg("name", help="HELP")]` const; `[arg("name", short="b")]`/`[arg("name", short)]` defaults to first char, `[arg("name", long="bar")]`/`[arg("name", long)]` defaults to param name, `[arg("name", value="VAL")]` flag (no value, may be expr >=1.54), both long+short allowed, `-abc` ≡ `-a -b -c`; variadic `*`/`+` as option repeatable per occurrence.

## 5 positional-args & export
`set positional-arguments` (or `[positional-arguments]` per-recipe): args as `$1`,`$2`,`$@`/`"$@"` (`$0`=recipe name for shell recipes); example `touch "$1"`; PowerShell needs `set shell:=['pwsh.exe','-CommandWithArgs']` then `@($args[1..])`; `set export` exports all args/vars as env; `$arg` prefix exports single param; `positional-arguments` defeats typo detection.

## 6 deps & parallelism
order: deps run before depender; each recipe+args runs at most once per invocation (dedup by recipe+args); `just test build` still runs `build` first; `just a a a` runs `A` once; `just test foo test bar` runs `build` twice if `test TEST: build`.
subsequent deps: `b: a && c d` runs `a` before `b`, `c d` after `b`.
recursion: `just c` inside recipe spawns new just process (recalculated assignments, possible double deps).
parallel: `[parallel] main: foo bar baz` parallelizes deps; `--jobs N` (1.56) limits; `num_jobs()` returns jobs or `[]`; shell-level parallel via `parallel` shebang: `#!/usr/bin/env -S parallel --shebang --ungroup --jobs {{num_cpus()}}`.

## 7 groups/aliases/private/conditionals
groups: `[group('name')]` on recipe/module, multiple groups allowed, listed by `just --list` grouped, `--unsorted` preserves file order, `--groups`/`--groups --unsorted` lists groups.
aliases: `alias b:=build` (may target `foo::bar` submodule or module >=1.55 `alias f:=frontend` then `just f build`).
private: `_*` or `[private]` hides from `--list`/`--summary`/`--choose`.
conditionals: `[linux]` `[macos]` `[windows]` `[unix]` `[freebsd]` `[openbsd]` `[netbsd]` `[dragonfly]` `[android]` on recipes/modules/aliases/vars/settings (>=1.56 any top-level), enabled if any attr matches current OS.
duplicates: `set allow-duplicate-recipes`/`set allow-duplicate-variables` last wins (false default); import depth: shallow overrides deep, same depth earlier import overrides later (stack order, bug #2540).

## 8 variables & expressions
vars: `name:="value"` module-level; `just --evaluate` prints all, `just --evaluate foo` single, `just --evaluate bob::bar` submodule (1.49), `--evaluate-format shell|just` (1.49) controls export format.
lazy: `set lazy` skips unused vars; `export` vars always evaluated.
exprs: usable in assignments, defaults, `{{…}}`; ops: `+` concat, `++` (lists) concat, `&&`/`||` coalesce (lists unstable, only `[]` false, `''` true; `[]&&x→[]`, `x&&y→y`, `[]||y→y`, `x||y→x`), `/` join with `/` (adds even if present, `/"b"`→`/b`, always `/` even on Windows, avoid UNC `\\`), `{{{{`→`{{`.
strings: `'single'` (no escapes), `"double"` (escapes `\r` `\"` `\n` `\\` `\t` `\u{1F916}` up to 6 hex, `\`+newline→empty), triple `'''`/`"""` indented (strip leading newline + common indent, then process escapes for double), `x'~/$VAR/${VAR}/${VAR:-DEF}/~USER'` shell-expanded at compile time (env `~`/`$VAR`), `f'hello {{name}}'` format strings with `{{expr}}` (use `{{{{` for literal).
lists: `set lists` (1.53 unstable); literals `[a,b,c]` flatten, `[]` empty; variadic params become lists; `{{list}}` joins with space; dep call `*(recipe *arg)` per element; `else` omitted → `[]`; `+`/`/` combine string×list elementwise, same-length lists pairwise, `++` list concat.

## 9 backticks & shell()
backtick `` `echo hi` `` and `shell('cmd', args…)` executed with `set shell`; `shell('echo $1', 'foo')` passes `args` as `$1`…`$@` (first arg is program name for `$@`); example `shell('cat $1', file)`; backtick in recipe scope does NOT inherit exported vars; `shell()` with `python -c` maps `sys.argv[2]` as first real arg.

## 10 sigils & quiet
recipe line prefixes: `@` no-echo (`set quiet` global, `[no-quiet]` override), `-` ignore-error, `?` guard (requires `set guards`), combinable `@-`; `[no-exit-message]`/`set no-exit-message` suppress failure, `[exit-message]` force.

## 11 shebang/script
shebang recipe: body starting `#!/usr/bin/env bash` extracted to temp file, single shell (cd persists), `set tempdir` controls dir.
script: `[script]`|`[script("python3")]`|`[script('mise','exec','node@22','--','node')]` executes as script; `set script-interpreter:=['sh','-eu']`/`['uv','run','--script']` default; `[extension(".py")]` extension; `set default-script` defaults all to script, `[shell]` overrides; `[script]` unstable cache only.

## 12 working directory
default: recipe runs in `justfile` directory; `[no-cd]`/`set no-cd` (1.51) runs in invocation directory; `[working-directory:'path']`/`set working-directory:='path'` (1.33, expr 1.51) override (relative to default workdir); `invocation_directory()`/`invocation_directory_native()` getters; `justfile()`/`justfile_directory()` root, `source_file()`/`source_directory()` (1.27) current import, `module_file()`/`module_directory()`/`module_path()` current mod; `set working-directory`/`no-cd` per-recipe attrs override global; note dotenv search & backtick not affected by `[no-cd]`.

## 13 shell config
`set shell:=["bash","-cu"]`|`["zsh","-cu"]`|`["powershell.exe","-c"]`|`["cmd.exe","/c"]`; Windows `set windows-shell`/`set windows-powershell` deprecated use `[windows] set shell`; CLI `--shell <cmd> --shell-arg <arg>`; per-recipe `[shell]` attribute; `cygpath.exe` used for `invocation_directory()` on Windows to produce `/` style.

## 14 env & dotenv
vars: `export FOO:="bar"`|`export PATH:="./node_modules/.bin:"+env("PATH")`; `[env("RUST_LOG","debug")]` per-recipe (expr 1.51); `unexport FOO` (1.29); `set export` all vars.
env getters: `env("KEY")` aborts if missing, `env("KEY","default")` fallback (aliases `env_var`, `env_var_or_default` deprecated).
dotenv: `set dotenv-load` (search `.env` upward), `set dotenv-filename:=".env.local"` (search upward), `set dotenv-path:="/abs/.env"` (only workdir, overrides filename), `set dotenv-required` error if missing, `set dotenv-override` env file overrides existing, `set dotenv-command:='sops -d .enc.env'`|`'mise env'` (runs with `shell`, loads stdout, may be multiple), CLI `--dotenv-path/-E`, `--dotenv-filename/-F`, `--dotenv-command` (repeatable); parent module env inherited, child may override (1.49); sharing between recipes: each line fresh shell, use `cd bar && cmd` or shebang/script.

## 15 organization
import: `import 'foo/bar.just'`|`import? 'opt.just'`|`import '~/x.just'` (~/→HOME), absolute or relative, recursive, duplicate import no error (1.37), allow-duplicate interplay; may be optional for remote fetch recipe.
mod: `mod bar` searches `bar.just`→`bar/mod.just`→`bar/justfile`→`bar/.justfile` (last two case-insensitive); `mod foo 'PATH'` explicit file/dir; `mod? foo` optional (missing disabled, dependent recipes disabled 1.52); multiple optional same name non-conflicting if at most one exists; isolated settings/vars/aliases; invocation `just bar b` or `just bar::b`; `just --list foo::bar`; `justfile()` still root, `module_file()` current; doc comment `# foo is great\nmod foo` appears in list.
fallback: `set fallback` searches parent justfiles if recipe not found, stops at `fallback=false`.
global: `--global-justfile`/`-g` order `$XDG_CONFIG_HOME/just/justfile`→`~/.config/just/justfile`→`~/justfile`→`~/.justfile`.
hidden: `justfile`/`.justfile` hides.
remote: `import?`+fetch recipe pattern.

## 16 CLI
`just --list` (alpha, `--unsorted` file order, `--list-heading <h>` empty suppresses, `--list-prefix <p>`), `just --list <mod>` (space/`::`), `just --summary` (concise, `--unsorted`), `just --show <r>`, `just --dump`/`--dump --dump-format json` (`--dump` honors `--justfile -`/`.md` to stdout), `just --fmt`/`--fmt --check` (exit 1 diff if unformatted), `--indentation`/`JUST_INDENTATION`/`set indentation`, `just --evaluate [var]`/`--evaluate-format`, `just --choose`/`--chooser <cmd>`/`$JUST_CHOOSER` (default fzf, skips private/args), `just --completions <sh>` (bash/elvish/fish/nushell/powershell/zsh; bash lazy `~/.local/share/bash-completion/completions/just`, fish `~/.config/fish/completions`, zsh `~/.zsh/completions/_just`+fpath, nushell save, elvish/powershell via rc), `just --man` (roff), `just --justfile <p>`, `--working-directory <d>`, `--set k v`/`k=v` (submodule `foo::bar=v`), `--shell`, `--dotenv-*`, `--timestamp`/`--timestamp-format <fmt>` (chrono strftime, `[timestamp]` attr 1.58 optional fmt), `--yes` confirms `[confirm]`, `--one` single invocation, `--jobs`, `-n`/`--dry-run`, `-g`, `--changelog`, `--clean [recipe]`/`--clean bar::bob`, `--no-cache`, `--unstable`/`JUST_UNSTABLE`, `--color`/`JUST_COLOR`, `--help`.

## 17 chooser/confirm/timestamp/signals/completions
chooser: reads recipe names from stdin, prints space-separated to stdout; invoked via shell; default recipe `default: @just --choose`; skips private/param/alias.
confirm: `[confirm]` (1.17)/`[confirm("prompt")]` (1.23, expr 1.49) requires tty confirmation, `--yes` overrides, dependents not run if denied.
timestamp: `--timestamp`/`[timestamp]`/`[timestamp('fmt')]` prefixes each command.
signals: `SIGHUP`/`SIGINT`/`SIGQUIT`/`SIGTERM` fatal; if child running waits then halts, `SIGTERM` forwarded (1.41); `[continue]` (1.54, no args→SIGINT, args `"SIGHUP"`…) continues if child exits 0; `SIGINFO` (BSD/macOS ctrl-t) prints pids (1.41); Windows treats ctrl-c as SIGINT.
fmt/dump: canonical formatting, `--fmt` overwrites justfile, `--dump` to stdout.

## 18 cache [unstable]
req `set unstable`+`[script]`; `just --clean` deletes `.justcache`; attr `[cache(inputs="a",outputs="b",extra=`cmd`,environment=['PATH'])]`; key fields `body,environment,executor,extension,extra,inputs,positional,recipe,working_directory`; `environment` default `export`/`unexport` vars, customizable `environment=['PATH']`; `inputs` BLAKE3 hashes, missing error; `outputs` must exist and non-empty entry to skip, error if not produced; file locks concurrent safe; `just -vv` prints key; bypass `--no-cache`.

## 19 attributes (full)
`[arg(ARG,help="H")]` (1.46, const 1.55), `[arg(ARG,long="L")]` (1.46), `[arg(ARG,long)]` defaults param name, `[arg(ARG,short="S")]` (1.46), `[arg(ARG,short)]` defaults first char, `[arg(ARG,pattern="RE")]` (1.45, const 1.55), `[arg(ARG,value=VAL)]` (1.46, expr 1.54) flag, `[arg(ARG,min="MIN")]`/`[arg(ARG,max="MAX")]` (1.56, requires `set lists`), `[cache]` (1.54), `[confirm]`/`[confirm(PROMPT)]`, `[continue(SIGNALS)]` (1.54), `[default]` (1.43), `[doc(DOC)]` (1.27, const 1.56) module/recipe, `[env(NAME,VALUE)]` (1.47, expr 1.51), `[extension(EXT)]` (1.32), `[exit-message]` (1.39), `[freebsd]`/`[dragonfly]`/`[android]`/`[openbsd]`/`[netbsd]` (1.47/1.38/1.50), `[group(NAME)]` (1.27) module/recipe, `[linux]`/`[macos]`/`[unix]`/`[windows]` (1.8), `[metadata(METADATA)]` (1.42), `[no-cd]` (1.9), `[no-exit-message]` (1.7), `[no-quiet]` (1.23), `[parallel]` (1.42), `[positional-arguments]` (1.29), `[private]` (1.10), `[script(COMMAND)]` (1.32), `[script]` (1.33), `[shell]` (1.52), `[timestamp]`/`[timestamp(FORMAT)]` (1.58), `[working-directory(PATH)]` (1.38, expr 1.51); multi attrs `[no-cd,private]` or separate lines, colon sugar `[group:'bar']`.

## 20 settings (full)
bool `allow-duplicate-recipes` false, `allow-duplicate-variables` false, `default-list` false (1.52), `default-script` false (1.52), `dotenv-command` string, `dotenv-filename` string, `dotenv-load` false, `dotenv-override` false, `dotenv-path` string, `dotenv-required` false, `export` false, `fallback` false, `guards` false (1.47), `ignore-comments` false, `indentation` string (1.56), `lazy` false (1.47), `lists` false (1.53 unstable), `minimum-version` string (1.55), `no-cd` false (1.51), `no-exit-message` false (1.39), `positional-arguments` false, `quiet` false, `script-interpreter` ['sh','-eu'] (1.33), `shell` [COMMAND,ARGS…], `tempdir` string, `unstable` false (1.31), `windows-powershell` false deprecated, `windows-shell` [...] deprecated, `working-directory` string (1.33); bool sugar `set NAME`; non-bool may be expr (no backtick/func).

## 21 functions
sys: `arch()` values aarch64/arm/asmjs/hexagon/mips/msp430/powerpc/powerpc64/s390x/sparc/wasm32/x86/x86_64/xcore, `num_cpus()` (1.15), `os()` android/bitrig/dragonfly/emscripten/freebsd/haiku/ios/linux/macos/netbsd/openbsd/solaris/windows, `os_family()` unix/windows.
ext: `shell(cmd,args…)` (1.27) via shell, `env(k)`/`env(k,default)` (1.15) alias `env_var*` deprecated, `require(name)` (1.39) PATH search aborts, `which(name)` (1.39, requires lists) returns [] if not found.
invoke: `is_dependency()` true/false, `num_jobs()` (1.56) or [], `recipe_name()` (1.53).
invocation: `invocation_directory()` cygpath `/` on Windows, `invocation_directory_native()` verbatim.
file: `justfile()` root, `justfile_directory()` parent, `source_file()` (1.27) current import, `source_directory()`, `module_file()` current mod, `module_directory()`, `module_path()` `::` path.
proc: `just_executable()`, `just_pid()`, `just_version()` (1.55).
str: `append(suffix,s)` (1.27), `prepend(prefix,s)` (1.27), `encode_uri_component(s)` (1.27), `quote(s)`, `replace(s,from,to)`, `replace_regex(s,regex,repl)` Rust regex, `trim(s)`/`trim_end`/`trim_end_match(s,sub)`/`trim_end_matches`/`trim_start`/`trim_start_match`/`trim_start_matches`; case `capitalize`/`kebabcase`/`lowercamelcase`/`lowercase`/`shoutykebabcase`/`shoutysnakecase`/`snakecase`/`titlecase`/`uppercamelcase`/`uppercase` (1.7).
path fallible: `absolute_path(p)`, `canonicalize(p)` (1.24), `extension(p)`, `file_name(p)`, `file_stem(p)`, `parent_directory(p)`, `without_extension(p)` halt on error; infallible `clean(p)`, `join(a,b…)` (`/` always, `join` uses OS sep `\` on Windows).
fs: `path_exists(p)` true/false, `read(p)` (1.39).
assert: `assert(COND,EXPR)` (1.27, expr optional 1.53), `error(msg)`.
hash: `blake3(s)` (1.25), `blake3_file(p)` (1.25), `sha256(s)`, `sha256_file(p)`, `uuid()`.
rand: `choose(n,alphabet)` (1.27) no repeats, `HEX` const.
datetime: `datetime(fmt)` (1.30), `datetime_utc(fmt)` (1.30) chrono strftime.
semver: `semver_matches(version,req)` (1.16) "true"/"false".
style: `style(styles)` (1.37) returns escape prefix, `style(styles,text)` (1.55) auto-reset; styles command/error/warning, colors black/blue/cyan/green/magenta/red/white/yellow, 256 0-255, 24-bit #RRGGBB/#RGB, props blink/bold/dim/hidden/italic/reverse/strikethrough/underline, streams stdout/stderr gated by --color, fg:/bg: prefix; use `NORMAL` reset.
userdirs (1.23, XDG on Unix): `cache_directory()`, `config_directory()`, `config_local_directory()`, `data_directory()`, `data_local_directory()`, `executable_directory()`, `home_directory()`, `runtime_directory()` Linux only; XDG fallback `if env('XDG_CONFIG_HOME','')=~'^/' {env('XDG_CONFIG_HOME')} else {home_directory()/'.config'}`.

## 22 constants
`HEX`="0123456789abcdef", `HEXLOWER` same, `HEXUPPER`="0123456789ABCDEF", `PATH_SEP` "/" "\" on Windows, `PATH_VAR_SEP` ":" ";" on Windows, `CLEAR`="\ec", `NORMAL`="\e[0m", `BOLD`="\e[1m", `ITALIC`="\e[3m", `UNDERLINE`="\e[4m", `INVERT`="\e[7m", `HIDE`="\e[8m", `STRIKETHROUGH`="\e[9m", `BLACK`="\e[30m", `RED`="\e[31m", `GREEN`="\e[32m", `YELLOW`="\e[33m", `BLUE`="\e[34m", `MAGENTA`="\e[35m", `CYAN`="\e[36m", `WHITE`="\e[37m", `BG_BLACK`="\e[40m"…`BG_WHITE`="\e[47m"; combine `BOLD+RED+BG_BLUE+NORMAL`; `CLEAR` like `clear`.

## 23 misc essentials
watchexec: `watchexec just foo` rerun on change.
alias: `alias j=just`.
print verbatim: `export FOO:='''…'''` + `printf %s "$FOO"`; use `quote()`/`encode_uri_component()`.
Windows paths: `absolute_path` etc return `\`; `cygpath` fallback; `justfile()` vs `invocation_directory()` cygpath behavior.
uv: `set script-interpreter:=['uv','run','--script']` + `[script]` with `# /// script\n# dependencies=["sh"]\n# ///`; shebang `#!/usr/bin/env -S uv run --script`.
mise: `set dotenv-command:='mise env'`+`set dotenv-override` (or `mise install -q && mise env`), per-recipe `[script('mise','exec','node@22','--','node')]` or `set shell:=['mise','exec','--','sh','-cu']` + `[env('MISE_NODE_VERSION','22')]`.
metadata: `[metadata("a","b")]` via `--dump --dump-format json`.
grammar: `https://github.com/casey/just/blob/master/GRAMMAR.md`; old `contrib/just.sh`.
