<div align="center">

<h1>Edio Downloader — 可爱的本地视频下载 WebApp</h1>

一个轻巧的本地 Web 界面，基于 yt‑dlp，支持快速粘贴链接下载、提取音频、字幕，以及在本机文件夹中打开下载目录。适合“点开即用、下载即走”的可爱风格桌面体验。

</div>

—

特性
- 本地运行，无账号、无云端依赖
- 多链接粘贴下载、进度条、实时日志
- 一键“在本机打开下载文件夹”，任务完成后自动刷新目录
- 支持字幕下载、缩略图嵌入、仅提取音频（需要 ffmpeg）
- 只展示最终产物文件，过滤临时分段和系统隐藏文件

系统要求
- Python 3.9+
- ffmpeg 已在 PATH 中

安装与启动（本机）
1) 可选：构建 `yt-dlp` 可执行（与 CLI 行为保持一致）
   
   ```bash
   make yt-dlp
   ```

2) 创建虚拟环境并安装小体量依赖
   
   ```bash
   python3 -m venv .venv
   .venv/bin/pip install -U pip Flask gunicorn
   ```

3) 启动 Web 服务（单进程，避免任务状态分散在多个进程）
   
   ```bash
   .venv/bin/gunicorn -w 1 -b 127.0.0.1:8080 webui.app:app \
     --pid webui/.webui.pid \
     --access-logfile webui/webui.log --error-logfile webui/webui.log --daemon
   ```

4) 打开浏览器访问 http://127.0.0.1:8080/

下载目录
- 默认目录：`webui_downloads/`
- 页面“下载目录（最近）”会自动列出已有文件（纯文本，不带链接）；点击下方按钮“在本机打开下载文件夹”即可在系统文件管理器中打开

环境变量
- `YTDLP_WEBUI_DOWNLOAD_DIR`：下载目录（默认 `./webui_downloads`）
- `YTDLP_WEBUI_HOST` / `YTDLP_WEBUI_PORT`：服务绑定地址/端口

小贴士
- Gunicorn 务必 `-w 1`。UI 将任务状态保存在进程内存，多进程会导致 `/api/status/<id>` 间歇 404
- 仅提取音频与缩略图嵌入需要 ffmpeg；UI 过滤 `.DS_Store` 与临时分段文件

常用维护命令
- 停止：`kill $(cat webui/.webui.pid)`
- 重启：`kill -HUP $(cat webui/.webui.pid)`
- 查看日志：`tail -f webui/webui.log`

开发者指南
- 代码组织、构建/测试规范见 `AGENTS.md`
- 仅跑静态检查：`make codetest`；离线测试：`make offlinetest`

致谢
- 本项目基于开源项目 [yt‑dlp](https://github.com/yt-dlp/yt-dlp)。若需完整 CLI 功能，请参考其文档与许可证（本仓库随附上游 LICENSE）。

