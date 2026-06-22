# `doc/_pending_sync/` 目录说明

本目录**不是**项目根 `README.md` 的副本，仅用于 **root 属主文件无法直接写入**时的临时中转。

## 工作原理

1. `python3 scripts/sync_all_docs.py` 尝试更新主文档（如根目录 `README.md`）。
2. 若遇 `PermissionError`，会把**当时脚本生成的内容**写入本目录下的同名路径，并登记到 `pending_apply.manifest`。
3. 修复属主后执行 `sudo bash scripts/apply_pending_docs.sh`，**仅合并 manifest 中的文件**。

## 禁止误操作

- **不要**把根目录 `README.md` 复制到本目录长期存放；副本会随主文档演进变**陈旧**，`apply_pending_docs.sh` 曾会整目录覆盖主文件（已修复为 manifest + 新旧校验）。
- **不要**将 `*-同步.md` 补丁说明与待合并副本混为一谈；补丁说明合入后删除，并记入 [已合并补丁记录.md](已合并补丁记录.md)。
- 本目录下的 `README.md`（本文件）与 `已合并补丁记录.md` **永远不会**被 `apply_pending_docs.sh` 覆盖到仓库其它路径。

## 相关文档

- [doc/文档同步说明.md](../文档同步说明.md)
- [scripts/apply_pending_docs.sh](../../scripts/apply_pending_docs.sh)
- [scripts/sync_all_docs.py](../../scripts/sync_all_docs.py)
