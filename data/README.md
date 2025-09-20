# 地学类期刊数据目录

本目录包含地学类期刊列表的结构化数据文件。

## 文件说明

### `journals_all.csv`
- **格式**: CSV (逗号分隔值)
- **编码**: UTF-8
- **列结构**:
  - `Index`: 期刊序号 (1-575)
  - `Journal Name`: 期刊名称
  - `ISSN`: 国际标准期刊号
  - `Category`: 期刊类别 (统一标记为"区")

### 当前状态
- ✅ 文件结构已创建且格式正确
- ✅ 包含20个知名地学期刊作为示例
- ⏳ 需要补充完整的575个期刊数据

### 示例数据
文件当前包含以下示例期刊：
1. Geology
2. Nature Geoscience  
3. Earth and Planetary Science Letters
4. Geochimica et Cosmochimica Acta
5. Journal of Geophysical Research: Solid Earth
6. ... (共20个示例期刊)

### 数据要求
为完成完整的575个期刊列表，需要提供：
- 期刊名称 (中文或英文)
- 有效的ISSN号 (格式: XXXX-XXXX)
- 按编号1-575的顺序排列
- 所有期刊统一标记为"区"类别

### 验证工具
可使用 `/tmp/validate_journals.py` 脚本验证数据格式和完整性：

```bash
python3 /tmp/validate_journals.py
```

### 更新说明
- 创建时间: 2025年9月
- 当前版本: v0.1 (模板版本)
- 目标版本: v1.0 (完整575期刊数据)