#!/bin/bash
# 自动更新 GitHub Action 版本脚本
# 用法:
#   update_action.sh                       # 更新 .github/workflows 下所有 Action 版本
#   update_action.sh <dir>                 # 更新指定目录下所有 yaml/yml 中所有 Action 版本
#   update_action.sh <dir> <action>        # 更新指定目录下所有 yaml/yml 中指定 Action 版本

# 获取第一个参数（目录）
TARGET_DIR="$1"

# 获取第二个参数（action 名称，可选）
ACTION_NAME="$2"

# 如果未指定目录，默认使用 .github/workflows
if [ -z "$TARGET_DIR" ]; then
    TARGET_DIR=".github/workflows"
fi

# 如果目录不存在，报错退出
if [ ! -d "$TARGET_DIR" ]; then
    echo "错误: 目录不存在: $TARGET_DIR"
    exit 1
fi

# 收集所有要更新的 yaml/yml 文件
mapfile -t FILES < <(find "$TARGET_DIR" -type f \( -name "*.yml" -o -name "*.yaml" \))

if [ ${#FILES[@]} -eq 0 ]; then
    echo "在 $TARGET_DIR 目录下未找到 yaml/yml 文件"
    exit 1
fi

echo "找到 ${#FILES[@]} 个文件"

# 如果指定了 action，只处理该 action；否则处理所有 action
if [ -n "$ACTION_NAME" ]; then
    # 获取指定 action 的最新版本
    LATEST_TAG=$(curl -s "https://api.github.com/repos/$ACTION_NAME/releases/latest" | grep '"tag_name":' | sed -E 's/.*"([^"]+)".*/\1/')

    if [ -z "$LATEST_TAG" ]; then
        echo "无法获取 $ACTION_NAME 的最新版本"
        exit 1
    fi

    MAJOR_VERSION=${LATEST_TAG%%.*}

    echo "将 $ACTION_NAME 更新为 $MAJOR_VERSION ($LATEST_TAG)"

    # 更新指定 action
    for FILE in "${FILES[@]}"; do
        # 检查文件是否包含该 action
        if grep -q "$ACTION_NAME@" "$FILE" 2>/dev/null; then
            echo "更新文件: $FILE"
            sed -i -E "s|($ACTION_NAME)@[vV]?[0-9]+|\1@$MAJOR_VERSION|g" "$FILE"
        fi
    done
else
    # 更新所有 action - 需要先收集所有用到的 action
    echo "扫描所有 Action 版本..."

    for FILE in "${FILES[@]}"; do
        # 提取文件中所有 uses 的 action 名称（去重）
        grep -oE 'uses:[[:space:]]*[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+@[vV]?[0-9.]+' "$FILE" 2>/dev/null | \
            sed -E 's/uses:[[:space:]]*//; s/@.*//' | sort -u | while read -r action; do
            # 获取该 action 的最新版本
            LATEST_TAG=$(curl -s "https://api.github.com/repos/$action/releases/latest" | grep '"tag_name":' | sed -E 's/.*"([^"]+)".*/\1/')

            if [ -n "$LATEST_TAG" ]; then
                MAJOR_VERSION=${LATEST_TAG%%.*}
                echo "将 $action 更新为 $MAJOR_VERSION ($LATEST_TAG) in $FILE"
                sed -i -E "s|($action)@[vV]?[0-9]+|\1@$MAJOR_VERSION|g" "$FILE"
            fi
        done
    done
fi

echo "完成！"