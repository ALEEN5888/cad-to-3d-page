# CAD 转三维网页

> 想从零上手、了解完整流程和备份方法，先看 [新手教程](新手教程.md)。

把 SolidWorks 导出的 STEP / IGES 模型，一键转成**单个 HTML 文件**的三维查看页。
收到文件的人双击就能用浏览器打开，不用装 CAD、不用联网、手机上也能转着看。

## 怎么用

双击 `转换.cmd`，在弹出的窗口里选中模型（可多选），确定。
也可以把模型文件直接拖到 `转换.cmd` 的图标上。

几秒到几分钟后，模型旁边会生成 `原文件名_三维查看.html`，并自动打开。

支持格式：STEP / STP / IGES / IGS / STL / OBJ / PLY / 3MF / GLB

如果出来的模型上下颠倒，改用 `转换_上下翻转.cmd`。

## 文件说明

| 文件 | 作用 |
| --- | --- |
| `转换.cmd` | 主入口（双击选文件，或拖拽） |
| `转换_上下翻转.cmd` | 模型上下颠倒时用，翻转 180° |
| `install-deps.cmd` | 依赖缺失时双击跑一次 |
| `make_viewer.py` | 主程序：网格化 → 分色 → 压缩 → 打包 |
| `pick_files.py` | 双击 `转换.cmd` 时的文件选择框 |
| `build_html.py` | 生成单文件网页（内嵌查看器与模型） |
| `colorize.py` | 给每个零件分配不同颜色 |
| `vendor/model-viewer.min.js` | Google model-viewer 查看器（Apache-2.0） |
| `说明.txt` | 完整中文说明（参数、原理、常见问题） |

## 依赖

- Python 3.9+
- `pip install cascadio trimesh`
- 可选：`npm install -g gltfpack`（压缩用，没有也能跑，只是文件约翻倍）

第一次用的电脑，双击 `install-deps.cmd` 自动装齐。

## 常用参数

```bash
python make_viewer.py 模型.STEP                 # 默认：相对公差 0.0004，目标 12 MB
python make_viewer.py 模型.STEP --flip-axis x   # 上下颠倒时翻转
python make_viewer.py 模型.STEP --target-mb 4   # 更小的预览版（允许圆管压粗）
python make_viewer.py 模型.STEP --mono          # 统一白模，不分色
```

`--tol-angular` 的单位是**弧度**。软件默认 0.5 弧度（28.6°）会让圆柱只剩 12 段，
明显发棱；本工具默认 0.15 弧度。

## 处理流程

```
STEP → OpenCASCADE 网格化 → 每零件独立材质上色
     → 顶点量化压缩（gltfpack） → base64 内嵌 + 查看器打包 → 单文件 HTML
```

## 说明

- 生成的 HTML 是自包含单文件，查看器代码和模型数据都在里面，断网也能打开。
- 每次重建的 HTML 都是全新的完整副本（没有增量），不适合反复提交进 git 历史；
  建议把成品放在 GitHub Releases 里，仓库只存源码和脚本。
- 文件里就是模型本体，发给谁谁就能提取几何，敏感图纸请谨慎分发。

## 许可

本项目以 [MIT License](LICENSE) 发布。`vendor/model-viewer.min.js` 是
Google 的 [model-viewer](https://github.com/google/model-viewer)，按 Apache-2.0
授权，其许可声明保留在文件头部。
