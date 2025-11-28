import sys
import os
from pathlib import Path
from datetime import datetime

import tkinter as tk
from tkinter import filedialog, ttk, messagebox

from PIL import Image
import piexif


def format_dt(dt: datetime | None) -> str:
    if not dt:
        return ""
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def read_exif_times(path: Path):
    """
    返回一个 dict：
    - mtime: Windows 文件系统的修改时间
    - exif_raw_*: 通过 _getexif() 读取到的原始 EXIF 时间（和服务器逻辑一致）
    - piexif_*: 通过 piexif + img.info['exif'] 读取到的时间
    """
    result = {
        "mtime": None,
        "exif_raw_original": "",
        "exif_raw_digitized": "",
        "exif_raw_datetime": "",
        "piexif_original": "",
        "piexif_digitized": "",
        "piexif_datetime": "",
    }

    # 1) 文件 mtime（本机 Windows 上的）
    try:
        st = path.stat()
        result["mtime"] = datetime.fromtimestamp(st.st_mtime)
    except Exception as e:
        print(f"[WARN] 读取 mtime 失败 {path}: {e}", file=sys.stderr)

    # 2) 通过 _getexif() 读取原始 EXIF（服务器 get_photo_time 使用的方式）
    try:
        with Image.open(path) as img:
            if hasattr(img, "_getexif") and img._getexif():
                exif_dict = img._getexif() or {}

                def get_tag(tag):
                    v = exif_dict.get(tag)
                    if v is None:
                        return ""
                    if isinstance(v, bytes):
                        return v.decode("utf-8", errors="ignore")
                    return str(v)

                # 36867: DateTimeOriginal
                # 36868: DateTimeDigitized
                # 306:   DateTime
                result["exif_raw_original"] = get_tag(36867)
                result["exif_raw_digitized"] = get_tag(36868)
                result["exif_raw_datetime"] = get_tag(306)
            else:
                print(f"[INFO] _getexif 没有返回 EXIF 数据: {path}", file=sys.stderr)

    except Exception as e:
        print(f"[WARN] _getexif 解析失败 {path}: {e}", file=sys.stderr)

    # 3) 通过 piexif + img.info['exif'] 读取（你之前工具用的方式）
    try:
        with Image.open(path) as img:
            if "exif" not in img.info:
                print(f"[INFO] img.info 中不含 'exif' 字段: {path}", file=sys.stderr)
                return result

            exif_dict = piexif.load(img.info["exif"])

            def get_str(ifd, tag):
                try:
                    value = exif_dict.get(ifd, {}).get(tag)
                    if value is None:
                        return ""
                    if isinstance(value, bytes):
                        return value.decode("utf-8", errors="ignore")
                    return str(value)
                except Exception:
                    return ""

            result["piexif_original"] = get_str(
                piexif.ExifIFD.DateTimeOriginal, piexif.ExifIFD.DateTimeOriginal
            )
            result["piexif_digitized"] = get_str(
                piexif.ExifIFD.DateTimeDigitized, piexif.ExifIFD.DateTimeDigitized
            )
            result["piexif_datetime"] = get_str(
                piexif.ImageIFD.DateTime, piexif.ImageIFD.DateTime
            )
    except Exception as e:
        print(f"[WARN] piexif 解析失败 {path}: {e}", file=sys.stderr)

    return result


def _write_exif_time_preserve_mtime(path: Path, target_dt: datetime):
    """将图片 EXIF 时间写为 target_dt，并在保存后恢复原始 atime/mtime。"""

    try:
        st = path.stat()
        orig_atime = st.st_atime
        orig_mtime = st.st_mtime
    except Exception as e:
        raise RuntimeError(f"读取 mtime 失败: {e}")

    dt_str = target_dt.strftime("%Y:%m:%d %H:%M:%S")  # EXIF 要求格式

    try:
        with Image.open(path) as img:
            # 如果已有 EXIF，则在原基础上修改；没有则新建一个
            if "exif" in img.info:
                exif_dict = piexif.load(img.info["exif"])
            else:
                exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}

        # 设置 EXIF 中的时间字段
        exif_dict.setdefault("Exif", {})[piexif.ExifIFD.DateTimeOriginal] = dt_str.encode("utf-8")
        # 同时更新 DateTimeDigitized 和 0th.DateTime，方便其他软件显示一致
        exif_dict.setdefault("Exif", {})[piexif.ExifIFD.DateTimeDigitized] = dt_str.encode("utf-8")
        exif_dict.setdefault("0th", {})[piexif.ImageIFD.DateTime] = dt_str.encode("utf-8")

        exif_bytes = piexif.dump(exif_dict)

        # 覆盖保存会临时改变 mtime
        with Image.open(path) as img:
            img.save(path, exif=exif_bytes)

        # 保存后把 atime/mtime 恢复成原来的值，避免动到文件系统时间
        os.utime(path, (orig_atime, orig_mtime))

    except Exception as e:
        raise RuntimeError(f"写入 EXIF 失败: {e}")


def sync_exif_to_mtime(path: Path):
    """将此图片的 EXIF 时间同步为当前文件 mtime（仅改 EXIF，不改文件系统时间）。"""
    try:
        st = path.stat()
        mtime = datetime.fromtimestamp(st.st_mtime)
    except Exception as e:
        raise RuntimeError(f"读取 mtime 失败: {e}")

    _write_exif_time_preserve_mtime(path, mtime)


class ExifViewer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("图片时间对比与同步工具（EXIF ⇆ Windows 修改时间）")
        self.geometry("1450x550")
        self.uniform_dt_var = tk.StringVar()
        self._build_ui()

    def _build_ui(self):
        # 顶部按钮区域
        top_frame = tk.Frame(self)
        top_frame.pack(fill=tk.X, padx=10, pady=5)

        btn_select = tk.Button(top_frame, text="选择图片...", command=self.select_files)
        btn_select.pack(side=tk.LEFT)

        btn_sync = tk.Button(
            top_frame,
            text="同步选中图片时间（用 mtime 覆盖 EXIF）",
            command=self.sync_selected,
            fg="white",
            bg="#d9534f",
        )
        btn_sync.pack(side=tk.LEFT, padx=10)

        # 自定义时间同步区域
        custom_frame = tk.Frame(self)
        custom_frame.pack(fill=tk.X, padx=10, pady=(0, 5))

        lbl_custom = tk.Label(
            custom_frame,
            text="自定义时间(YYYY-MM-DD HH:MM:SS)：",
            anchor="w",
        )
        lbl_custom.pack(side=tk.LEFT)

        entry_custom = tk.Entry(custom_frame, textvariable=self.uniform_dt_var, width=25)
        entry_custom.pack(side=tk.LEFT, padx=5)

        btn_apply_custom = tk.Button(
            custom_frame,
            text="应用到选中图片(EXIF)",
            command=self.apply_uniform_time_to_selected,
        )
        btn_apply_custom.pack(side=tk.LEFT, padx=5)

        lbl_tip = tk.Label(
            top_frame,
            text="提示：同步会修改文件本身的 EXIF 时间字段，操作前请自行备份原始照片。",
            anchor="w",
            fg="#555",
        )
        lbl_tip.pack(side=tk.LEFT, padx=10)

        # 表格列定义
        columns = (
            "path",
            "mtime",
            "exif_raw_original",
            "exif_raw_digitized",
            "exif_raw_datetime",
            "piexif_original",
            "piexif_digitized",
            "piexif_datetime",
        )

        self.tree = ttk.Treeview(self, columns=columns, show="headings", selectmode="extended")

        self.tree.heading("path", text="文件路径")
        self.tree.heading("mtime", text="文件修改时间(mtime)")
        self.tree.heading("exif_raw_original", text="_getexif DateTimeOriginal (36867)")
        self.tree.heading("exif_raw_digitized", text="_getexif DateTimeDigitized (36868)")
        self.tree.heading("exif_raw_datetime", text="_getexif DateTime (306)")
        self.tree.heading("piexif_original", text="piexif DateTimeOriginal")
        self.tree.heading("piexif_digitized", text="piexif DateTimeDigitized")
        self.tree.heading("piexif_datetime", text="piexif ImageIFD.DateTime")

        self.tree.column("path", width=350, anchor="w")
        self.tree.column("mtime", width=150, anchor="center")
        self.tree.column("exif_raw_original", width=180, anchor="center")
        self.tree.column("exif_raw_digitized", width=180, anchor="center")
        self.tree.column("exif_raw_datetime", width=180, anchor="center")
        self.tree.column("piexif_original", width=180, anchor="center")
        self.tree.column("piexif_digitized", width=180, anchor="center")
        self.tree.column("piexif_datetime", width=180, anchor="center")

        # 垂直滚动条
        vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        # 水平滚动条
        hsb = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(xscrollcommand=hsb.set)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)

        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

    def select_files(self):
        filetypes = [
            ("Images", "*.jpg;*.jpeg;*.png;*.gif;*.tif;*.tiff;*.webp"),
            ("All files", "*.*"),
        ]
        paths = filedialog.askopenfilenames(
            title="选择图片文件", filetypes=filetypes
        )
        if not paths:
            return

        # 清空旧记录
        for item in self.tree.get_children():
            self.tree.delete(item)

        for p in paths:
            self._insert_file(Path(p))

    def _insert_file(self, path: Path):
        info = read_exif_times(path)

        self.tree.insert(
            "",
            tk.END,
            values=(
                str(path),
                format_dt(info["mtime"]),
                info["exif_raw_original"],
                info["exif_raw_digitized"],
                info["exif_raw_datetime"],
                info["piexif_original"],
                info["piexif_digitized"],
                info["piexif_datetime"],
            ),
        )

    def sync_selected(self):
        items = self.tree.selection()
        if not items:
            messagebox.showinfo("提示", "请先在表格中选中至少一张图片。")
            return

        if not messagebox.askyesno(
            "确认操作",
            "将把选中图片的 EXIF 日期统一改为当前文件的修改时间(mtime)。\n"
            "这会直接修改原始文件，建议先备份。\n\n是否继续？",
        ):
            return

        errors = []
        for item in items:
            values = self.tree.item(item, "values")
            path_str = values[0]
            path = Path(path_str)

            try:
                sync_exif_to_mtime(path)
                # 同步后重新读取并更新这一行显示
                info = read_exif_times(path)
                new_values = (
                    str(path),
                    format_dt(info["mtime"]),
                    info["exif_raw_original"],
                    info["exif_raw_digitized"],
                    info["exif_raw_datetime"],
                    info["piexif_original"],
                    info["piexif_digitized"],
                    info["piexif_datetime"],
                )
                self.tree.item(item, values=new_values)
            except Exception as e:
                errors.append(f"{path}: {e}")

        if errors:
            messagebox.showerror(
                "部分失败",
                "以下文件同步失败：\n\n" + "\n".join(errors[:10]) + ("\n..." if len(errors) > 10 else ""),
            )
        else:
            messagebox.showinfo("完成", "选中图片的 EXIF 日期已全部同步为 mtime。")

    def apply_uniform_time_to_selected(self):
        dt_str = self.uniform_dt_var.get().strip()
        if not dt_str:
            messagebox.showwarning("提示", "请先在上方输入要统一设置的时间，例如 2020-01-01 12:00:00")
            return

        try:
            target_dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            messagebox.showerror("格式错误", "时间格式不正确，请使用 YYYY-MM-DD HH:MM:SS")
            return

        items = self.tree.selection()
        if not items:
            messagebox.showinfo("提示", "请先在表格中选中至少一张图片。")
            return

        if not messagebox.askyesno(
            "确认操作",
            "将把选中图片的 EXIF 日期统一改为你输入的时间。\n"
            "这会直接修改原始文件，但会保留文件系统的修改时间(mtime)。\n\n是否继续？",
        ):
            return

        errors = []
        updated = 0
        for item in items:
            values = self.tree.item(item, "values")
            path_str = values[0]
            path = Path(path_str)

            try:
                _write_exif_time_preserve_mtime(path, target_dt)
                # 同步后重新读取并更新这一行显示
                info = read_exif_times(path)
                new_values = (
                    str(path),
                    format_dt(info["mtime"]),
                    info["exif_raw_original"],
                    info["exif_raw_digitized"],
                    info["exif_raw_datetime"],
                    info["piexif_original"],
                    info["piexif_digitized"],
                    info["piexif_datetime"],
                )
                self.tree.item(item, values=new_values)
                updated += 1
            except Exception as e:
                errors.append(f"{path}: {e}")

        if errors:
            messagebox.showerror(
                "部分失败",
                f"共 {updated} 个文件更新成功，部分文件更新失败：\n\n"
                + "\n".join(errors[:10])
                + ("\n..." if len(errors) > 10 else ""),
            )
        else:
            messagebox.showinfo("完成", f"已将 {updated} 个文件的 EXIF 日期统一设置为 {dt_str}。")


def main():
    root = ExifViewer()
    root.mainloop()


if __name__ == "__main__":
    main()