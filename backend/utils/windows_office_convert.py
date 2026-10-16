"""Windows 原生旧版 Office 转换；在独立进程内运行，受 Worker 超时限制。"""

import sys
from pathlib import Path


def convert(source, target):
    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()
    app = document = None
    try:
        source, target = Path(source).resolve(), Path(target).resolve()
        if source.suffix.lower() == ".doc":
            app = win32com.client.DispatchEx("Word.Application")
            app.Visible = False
            app.DisplayAlerts = 0
            app.AutomationSecurity = 3
            document = app.Documents.Open(str(source), ReadOnly=True, AddToRecentFiles=False)
            document.SaveAs2(str(target), FileFormat=16)
        elif source.suffix.lower() == ".ppt":
            app = win32com.client.DispatchEx("PowerPoint.Application")
            app.DisplayAlerts = 1
            app.AutomationSecurity = 3
            document = app.Presentations.Open(str(source), ReadOnly=True, Untitled=False, WithWindow=False)
            document.SaveAs(str(target), 24)
        else:
            raise ValueError("仅支持 .doc 和 .ppt 转换")
    finally:
        if document is not None:
            document.Close()
        if app is not None:
            app.Quit()
        pythoncom.CoUninitialize()


if __name__ == "__main__":
    convert(sys.argv[1], sys.argv[2])
