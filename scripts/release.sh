#!/bin/sh
# 一键发布 vX.Y.Z 到 GitHub Release（源码 zip 方式，本项目标准发布流程）。
# 用法: ./scripts/release.sh [版本号]    默认读取 app/version.py 的 VERSION
# 前置: gh 已认证（gh auth status）；当前分支已提交推送。
set -e
cd "$(dirname "$0")/.."

# 1) 版本号
VERSION=${1:-$(sed -n 's/^VERSION = "\(.*\)"/\1/p' app/version.py)}
if [ -z "$VERSION" ]; then
  echo "!! 无法确定版本号（app/version.py 或参数）" >&2; exit 1
fi
TAG="v$VERSION"
ZIP="/tmp/av-agent-$VERSION.zip"
echo "== 发布版本: $TAG =="

# 2) 校验工作区干净
if [ -n "$(git status --porcelain)" ]; then
  echo "!! 工作区有未提交改动，请先提交推送" >&2; exit 1
fi

# 3) 打包源码 zip（含 desktop/assets/fonts 字体，不含 .git/venv/运行产物）
git archive --format=zip --prefix="av-agent-$VERSION/" HEAD -o "$ZIP"
echo "== 已打包: $ZIP ($(du -h "$ZIP" | cut -f1)) =="

# 4) 创建或更新 release
if gh release view "$TAG" >/dev/null 2>&1; then
  echo "== Release $TAG 已存在，更新（保留草稿状态，重新上传资产） =="
  gh release edit "$TAG" --notes "$(cat /tmp/av-release-notes.md 2>/dev/null || echo 'AV Agent v$VERSION')" >/dev/null 2>&1 || true
else
  echo "== 创建 Release $TAG（draft） =="
  gh release create "$TAG" --draft --title "v$VERSION" --notes "AV Agent v$VERSION" >/dev/null
fi

# 5) 上传 zip（覆盖旧资产）
gh release delete-asset "$TAG" "av-agent-$VERSION.zip" >/dev/null 2>&1 || true
gh release upload "$TAG" "$ZIP" --clobber
echo "== 已上传资产: av-agent-$VERSION.zip =="

# 6) 发布（draft -> 正式）
gh release edit "$TAG" --draft=false >/dev/null 2>&1 || \
  gh release edit "$TAG" --draft=false
echo "== 已发布: https://github.com/wzcawzc123/av-agent/releases/tag/$TAG =="
