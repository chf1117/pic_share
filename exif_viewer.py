import sys
from pathlib import Path
from datetime import datetime
import os
import time

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


class ExifViewer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("图片时间对比工具（EXIF vs Windows 修改时间）")
        self.geometry("1400x500")
        self.uniform_dt_var = tk.StringVar()
        self._build_ui()

    def _build_ui(self):
        # 顶部按钮区域
        top_frame = tk.Frame(self)
        top_frame.pack(fill=tk.X, padx=10, pady=5)

        btn_select = tk.Button(top_frame, text="选择图片...", command=self.select_files)
        btn_select.pack(side=tk.LEFT)

        lbl_tip = tk.Label(
            top_frame,
            text="一次可选多张图片，对比：Windows 修改时间 / _getexif EXIF / piexif EXIF",
            anchor="w",
        )
        lbl_tip.pack(side=tk.LEFT, padx=10)

        # 统一时间设置区域
        uniform_frame = tk.Frame(self)
        uniform_frame.pack(fill=tk.X, padx=10, pady=(0, 5))

        lbl_uniform = tk.Label(
            uniform_frame,
            text="统一时间(YYYY-MM-DD HH:MM:SS)：",
            anchor="w",
        )
        lbl_uniform.pack(side=tk.LEFT)

        entry_uniform = tk.Entry(uniform_frame, textvariable=self.uniform_dt_var, width=25)
        entry_uniform.pack(side=tk.LEFT, padx=5)

        btn_apply_uniform = tk.Button(
            uniform_frame,
            text="应用到选中照片(EXIF)",
            command=self.apply_uniform_time_to_selected,
        )
        btn_apply_uniform.pack(side=tk.LEFT, padx=5)

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

        self.tree = ttk.Treeview(self, columns=columns, show="headings")

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
            path = Path(p)
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

    def apply_uniform_time_to_selected(self):
        dt_str = self.uniform_dt_var.get().strip()
        if not dt_str:
            messagebox.showwarning("提示", "请先在顶部输入要统一设置的时间，例如 2020-01-01 12:00:00")
            return

        try:
            dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            messagebox.showerror("格式错误", "时间格式不正确，请使用 YYYY-MM-DD HH:MM:SS")
            return

        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning("提示", "请先在表格中选中至少一张照片")
            return

        # EXIF 需要的时间格式："YYYY:MM:DD HH:MM:SS"
        exif_time_str = dt.strftime("%Y:%m:%d %H:%M:%S")

        updated_count = 0
        errors = []

        for item_id in selected_items:
            values = self.tree.item(item_id, "values")
            if not values:
                continue
            path_str = values[0]
            path = Path(path_str)
            if not path.exists():
                errors.append(f"文件不存在: {path_str}")
                continue

            # 记录原始 mtime
            try:
                st = path.stat()
                orig_atime = st.st_atime
                orig_mtime = st.st_mtime
            except Exception as e:
                errors.append(f"读取 mtime 失败 {path_str}: {e}")
                continue

            try:
                # 使用 piexif 写入 EXIF
                with Image.open(path) as img:
                    exif_bytes = img.info.get("exif")
                    if exif_bytes:
                        exif_dict = piexif.load(exif_bytes)
                    else:
                        exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "Interop": {}, "1st": {}, "thumbnail": None}

                # 设置 EXIF 时间字段
                exif_dict.setdefault("Exif", {})[piexif.ExifIFD.DateTimeOriginal] = exif_time_str.encode("utf-8")
                exif_dict.setdefault("Exif", {})[piexif.ExifIFD.DateTimeDigitized] = exif_time_str.encode("utf-8")
                exif_dict.setdefault("0th", {})[piexif.ImageIFD.DateTime] = exif_time_str.encode("utf-8")

                exif_bytes_new = piexif.dump(exif_dict)

                # 保存回文件
                with Image.open(path) as img:
                    img.save(path, exif=exif_bytes_new)

                # 恢复原始 atime / mtime（不改文件系统时间）
                try:
                    os.utime(path, (orig_atime, orig_mtime))
                except Exception as e:
                    errors.append(f"恢复文件时间失败 {path_str}: {e}")

                updated_count += 1

            except Exception as e:
                errors.append(f"写入 EXIF 失败 {path_str}: {e}")

        # 更新界面中的显示数据（重新读取选中项的 EXIF 信息）
        if updated_count > 0:
            for item_id in selected_items:
                values = self.tree.item(item_id, "values")
                if not values:
                    continue
                path_str = values[0]
                path = Path(path_str)
                if not path.exists():
                    continue
                info = read_exif_times(path)
                self.tree.item(
                    item_id,
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

        msg = f"已更新 {updated_count} 个文件的 EXIF 时间。"
        if errors:
            msg += "\n\n以下文件出现错误（不会影响其他文件）：\n" + "\n".join(errors)
        messagebox.showinfo("完成", msg)


def main():
    root = ExifViewer()
    root.mainloop()


if __name__ == "__main__":
    main()